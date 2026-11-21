/// Web2API Typed Exceptions
class Web2ApiException implements Exception {
  final String message;
  final int? statusCode;

  Web2ApiException(this.message, {this.statusCode});

  @override
  String toString() => 'Web2ApiException: $message (status: $statusCode)';
}

class Web2ApiAuthException extends Web2ApiException {
  Web2ApiAuthException([String message = 'Unauthorized: Invalid or missing API key.'])
      : super(message, statusCode: 401);
}

class Web2ApiExtensionUnavailableException extends Web2ApiException {
  Web2ApiExtensionUnavailableException([String message = 'Browser extension is not connected to the server.'])
      : super(message, statusCode: 503);
}

class Web2ApiTimeoutException extends Web2ApiException {
  Web2ApiTimeoutException([String message = 'Request timed out waiting for the browser AI interface.'])
      : super(message, statusCode: 504);
}

class Web2ApiConnectionException extends Web2ApiException {
  Web2ApiConnectionException(String message) : super('Failed to connect to Web2API: $message');
}
