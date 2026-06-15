_url = None


def setup_tunnel(port: int):
    global _url
    from backend.config import NGROK_AUTHTOKEN
    if not NGROK_AUTHTOKEN:
        return None
    try:
        from pyngrok import ngrok, conf
        conf.get_default().auth_token = NGROK_AUTHTOKEN
        tunnel = ngrok.connect(port, "http", bind_tls=True)
        _url = tunnel.public_url
        return _url
    except Exception as e:
        logging.getLogger("mimo-tg").error(f"Tunnel failed: {e}")
        return None


def get_url():
    return _url


def close_tunnel():
    global _url
    if _url:
        try:
            from pyngrok import ngrok
            ngrok.disconnect(_url)
        except Exception:
            pass
        _url = None
