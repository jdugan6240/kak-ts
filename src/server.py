import config
from kakoune import KakConnection
import logging
from tree_sitter import Language, Parser


class BufLanguage:
    def __init__(self, name, grammar, queries):
        self.lang = Language(grammar, name)
        with open(queries, "r") as query_file:
            self.queries = query_file.read()


class Buffer:
    def __init__(self):
        self.lang = None
        self.contents = ""
        self.tree = None


class Spec:
    def __init__(self, start, end, face):
        self.start = start
        self.end = end
        self.face = face

    def __str__(self):
        return f"{self.start[0] + 1}.{self.start[1] + 1},{self.end[0] + 1}.{self.end[1]}|{self.face}"

    def __repr__(self):
        return f"{self.start[0] + 1}.{self.start[1] + 1},{self.end[0] + 1}.{self.end[1]}|{self.face}"


kak_connection = None  # The connection to the Kakoune session
current_session = None  # The current Kakoune session
buffers = {}  # The set of buffers we're handling
languages = {}  # The configured languages
faces = {}  # The configured faces


def parse_config():
    conf = config.load_config()
    for lang in conf["languages"]:
        name = lang["name"]
        lib = lang["lib"]
        queries = lang["queries"]
        languages[name] = BufLanguage(name, lib, queries)
    for face in conf["faces"]:
        faces[face] = conf["faces"][face]


def update_tree(buffer):
    parser = Parser()
    parser.set_language(buffer.lang.lang)
    buffer.tree = parser.parse(bytes(buffer.contents, "utf8"))


def quit(session):
    # This should only be called when Kakoune is exiting.
    # So, we just need to clean up the sockets and exit.
    kak_connection.cleanup()
    exit(0)


def highlight_buffer(cmd):
    if cmd["buf"] in buffers.keys():
        buf = buffers[cmd["buf"]]
        language = buf.lang
        query = language.lang.query(language.queries)
        captures = query.captures(buf.tree.root_node)
        # Loop over all captures
        specs = []
        names = []
        prev_line = -1
        prev_char = -1
        for capture in captures:
            node = capture[0]
            # Keep trying until we get a result
            node_name_raw = capture[1]
            if node_name_raw not in names:
                names.append(node_name_raw)
            while True:
                logging.debug(f"Trying {node_name_raw}")
                if node_name_raw in faces.keys():
                    face = faces[node_name_raw]
                    start = node.start_point
                    end = node.end_point
                    # Sometimes, we can get repeat specs.
                    # So, we just try to skip those we've already done.
                    if start[1] < prev_char and start[0] <= prev_line:
                        break
                    prev_line = end[0]
                    prev_char = end[1]
                    specs.append(Spec(start, end, face))
                    break
                if "." not in node_name_raw:
                    break
                node_name_raw = ".".join(node_name_raw.split(".")[0:-1])
        # Now send specs to Kakoune
        specs_str = ""
        for spec in specs:
            specs_str += f"'{spec}' "
        kak_command = f"evaluate-commands -no-hooks -buffer {cmd['buf']} %[ set-option buffer tree_sitter_ranges %val{{timestamp}} {specs_str} ]"
        kak_connection.send_cmd(kak_command)


def parse_buffer(cmd):
    if cmd["buf"] in buffers.keys():
        buf = buffers[cmd["buf"]]
        with open(kak_connection.buf_fifo_path, 'r') as fifo:
            buf.contents = fifo.read()
        update_tree(buf)


def new_buffer(cmd):
    logging.debug(f"Creating new buffer with name {cmd['name']} and language {cmd['lang']}")
    buf = Buffer()
    buf.lang = languages[cmd["lang"]]

    buffers[cmd["name"]] = buf

    kak_command = f"evaluate-commands -no-hooks -buffer {cmd['name']} %[ tree-sitter-buffer-ready ]"
    logging.debug(kak_command)
    kak_connection.send_cmd(kak_command)


def handle_kak_command(cmd):
    logging.debug(f"Received command: {cmd}")
    if cmd["cmd"] == "stop":
        quit(current_session)
    elif cmd["cmd"] == "new":
        new_buffer(cmd)
    elif cmd["cmd"] == "parse":
        parse_buffer(cmd)
    elif cmd["cmd"] == "highlight":
        highlight_buffer(cmd)


def start(session, buf, ft):
    global kak_connection, current_session

    current_session = session

    kak_connection = KakConnection(session)

    kak_connection.send_cmd("set-option global tree_sitter_running true")
    kak_connection.send_cmd(
        f'set-option global tree_sitter_req_fifo "{kak_connection.in_fifo_path}"'
    )
    kak_connection.send_cmd(
        f'set-option global tree_sitter_buf_fifo "{kak_connection.buf_fifo_path}"'
    )

    parse_config()

    new_buffer({"name": buf, "lang": ft})

    # Begin listening for Kakoune messages
    while kak_connection.is_open:
        msg = kak_connection.get_msg()
        handle_kak_command(msg)
