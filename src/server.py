from kakoune import KakConnection
import logging
import time
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
        return f"{self.start[0] + 1}.{self.start[1] + 1},{self.end[0] + 1}.{self.end[1] + 1}|{self.face}"

    def __repr__(self):
        return f"{self.start[0] + 1}.{self.start[1] + 1},{self.end[0] + 1}.{self.end[1] + 1}|{self.face}"


kak_connection = None  # The connection to the Kakoune session
current_session = None  # The current Kakoune session
buffers = {}  # The set of buffers we're handling
languages = {
    "python": BufLanguage(
        "python",
        "/home/jdugan/.config/helix/runtime/grammars/python.so",
        "/home/jdugan/.config/helix/runtime/queries/python/highlights.scm",
    )
}  # The set of languages we support
faces = {
    "attribute": "meta",
    "comment": "comment",
    "function": "function",
    "keyword": "keyword",
    "operator": "operator",
    "string": "string",
    "type": "type",
    "type-builtin": "type",
    "constructor": "value",
    "constant": "value",
    "constant-builtin": "value",
    "punctuation": "operator"
}


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
        logging.debug(f"Captures: {captures}")
        for capture in captures:
            node = capture[0]
            node_name = capture[1].split(".")[0]
            if node_name in faces.keys():
                face = faces[node_name]
                start = node.start_point
                end = node.end_point
                specs.append(Spec(start, end, face))
        # Now send specs to Kakoune
        logging.debug(f"Specs: {specs}")
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

    new_buffer({"name": buf, "lang": ft})

    # Begin listening for Kakoune messages
    while kak_connection.is_open:
        msg = kak_connection.get_msg()
        handle_kak_command(msg)
