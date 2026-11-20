import logging
import webbrowser

from werkzeug.serving import make_server

from app import app

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with make_server("127.0.0.1", 0, app, threaded=True) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        logging.info("CLIPRO beží na %s. Okno terminálu nechaj otvorené.", url)
        webbrowser.open(url)
        server.serve_forever()
