import webbrowser

from werkzeug.serving import make_server

from app import app

if __name__ == "__main__":
    with make_server("127.0.0.1", 0, app, threaded=True) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"CLIPRO beží na {url}. Okno terminálu nechaj otvorené.", flush=True)
        webbrowser.open(url)
        server.serve_forever()
