#!/data/data/com.termux/files/usr/bin/sh
# Web2API auto-start for the Termux:Boot app.
# install-termux.sh --boot copies this file to ~/.termux/boot/web2api.
# Change WEB2API_MODE to "tailscale" if you connect over Tailscale instead of SSH.
termux-wake-lock
cd "__WEB2API_ROOT__" || exit 1
WEB2API_MODE="${WEB2API_MODE:-ssh}" nohup bash scripts/android/start-android.sh \
    > "$HOME/web2api.log" 2>&1 &
