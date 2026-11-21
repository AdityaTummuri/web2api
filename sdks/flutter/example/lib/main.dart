import 'package:flutter/material.dart';
import 'package:web2api/web2api.dart';

void main() {
  runApp(const Web2ApiExampleApp());
}

class Web2ApiExampleApp extends StatelessWidget {
  const Web2ApiExampleApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Web2API Flutter Demo',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.deepPurple),
        useMaterial3: true,
      ),
      home: const ChatScreen(),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  // Connect to standalone Web2API server
  // On Android Emulator: use 'http://10.0.2.2:8000'
  // On iOS Simulator / Desktop: use 'http://127.0.0.1:8000'
  // On Physical Device: use your PC's LAN IP e.g. 'http://192.168.1.100:8000'
  final client = Web2ApiClient(baseUrl: 'http://10.0.2.2:8000');

  final TextEditingController _controller = TextEditingController();
  final List<Map<String, String>> _messages = [];
  bool _isStreaming = false;

  void _sendMessage() async {
    final prompt = _controller.text.trim();
    if (prompt.isEmpty) return;

    setState(() {
      _messages.add({'sender': 'User', 'text': prompt});
      _messages.add({'sender': 'AI', 'text': ''});
      _isStreaming = true;
    });
    _controller.clear();

    final aiMsgIndex = _messages.length - 1;

    try {
      final buffer = StringBuffer();
      await for (final token in client.chatStream(prompt, model: 'gemini-pro')) {
        buffer.write(token);
        setState(() {
          _messages[aiMsgIndex]['text'] = buffer.toString();
        });
      }
    } catch (e) {
      setState(() {
        _messages[aiMsgIndex]['text'] = 'Error: $e';
      });
    } finally {
      setState(() {
        _isStreaming = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Web2API Live Streaming'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            tooltip: 'Reset Thread',
            onPressed: () async {
              await client.resetConversation();
              setState(() => _messages.clear());
            },
          )
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _messages.length,
              itemBuilder: (context, index) {
                final msg = _messages[index];
                final isUser = msg['sender'] == 'User';
                return Align(
                  alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.symmetric(vertical: 4),
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: isUser ? Colors.deepPurple[100] : Colors.grey[200],
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(msg['text'] ?? ''),
                  ),
                );
              },
            ),
          ),
          if (_isStreaming)
            const Padding(
              padding: EdgeInsets.all(8.0),
              child: LinearProgressIndicator(),
            ),
          Padding(
            padding: const EdgeInsets.all(8.0),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _controller,
                    decoration: const InputDecoration(
                      hintText: 'Type prompt for Gemini / ChatGPT / Claude...',
                      border: OutlineInputBorder(),
                    ),
                    onSubmitted: (_) => _sendMessage(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton(
                  icon: const Icon(Icons.send),
                  onPressed: _isStreaming ? null : _sendMessage,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
