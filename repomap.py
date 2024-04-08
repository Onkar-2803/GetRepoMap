import os
from collections import namedtuple
from pathlib import Path
import tiktoken
import pkg_resources
from grep_ast import TreeContext, filename_to_lang
from pygments.lexers import guess_lexer_for_filename
from pygments.token import Token
from pygments.util import ClassNotFound
from tree_sitter_languages import get_language, get_parser


Tag = namedtuple("Tag", "rel_fname fname line name kind".split())


class RepoMap:
    def __init__(
        self,
        root=None,
        main_model="gpt-4",
    ):
        self.root = root
        self.tokenizer = tiktoken.encoding_for_model(main_model)

    def read_text_in(self, fname):
        with open(str(fname), "r", encoding="utf-8") as f:
            return f.read()

    def get_repo_map(self, other_files):
        
        # other_files[0] because only one file.
        rel_fname = self.get_rel_fname(other_files[0])     #Gets name of file
        tags = list(self.get_tags_raw(other_files[0], rel_fname))
        repo_content = self.to_tree(tags)

        return repo_content

    def get_rel_fname(self, fname):
        return os.path.relpath(fname, self.root)
    

    def get_tags_raw(self, fname, rel_fname):
        lang = filename_to_lang(fname)
        if not lang:
            print('Language Not Supported')
            return

        language = get_language(lang)
        parser = get_parser(lang)

        # Load the tags queries
        try:
            scm_fname = pkg_resources.resource_filename(
                __name__, os.path.join("queries", f"tree-sitter-{lang}-tags.scm")
            )
        except KeyError:
            'SCM File absent'
            return
        
        query_scm = Path(scm_fname)
        if not query_scm.exists():
            return
        
        query_scm = query_scm.read_text()

        code = self.read_text_in(fname)
        if not code:
            'Code File Empty'
            return
        tree = parser.parse(bytes(code, "utf-8"))

        # Run the tags queries
        query = language.query(query_scm)
        captures = query.captures(tree.root_node)
        captures = list(captures)

        saw = set()
        for node, tag in captures:
            if tag.startswith("name.definition."):
                kind = "def"
            elif tag.startswith("name.reference."):
                kind = "ref"
            else:
                continue

            saw.add(kind)

            result = Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=node.text.decode("utf-8"),
                kind=kind,
                line=node.start_point[0],
            )

            yield result

        if "ref" in saw:
            return
        if "def" not in saw:
            return

        # We saw defs, without any refs
        # Some tags files only provide defs (cpp, for example)
        # Use pygments to backfill refs

        try:
            lexer = guess_lexer_for_filename(fname, code)
        except ClassNotFound:
            return

        tokens = list(lexer.get_tokens(code))
        tokens = [token[1] for token in tokens if token[0] in Token.Name]

        for token in tokens:
            yield Tag(
                rel_fname=rel_fname,
                fname=fname,
                name=token,
                kind="ref",
                line=-1,
            )

    def to_tree(self, tags):
        tags = sorted(tags)

        cur_fname = None
        context = None
        output = ""

        # add a bogus tag at the end so we trip the this_fname != cur_fname...
        dummy_tag = (None,)
        for tag in tags + [dummy_tag]:
            this_rel_fname = tag[0]

            # ... here ... to output the final real entry in the list
            if this_rel_fname != cur_fname:
                if context:
                    context.add_context()
                    output += "\n"
                    output += cur_fname + ":\n"
                    output += context.format()
                    context = None
                elif cur_fname:
                    output += "\n" + cur_fname + "\n"

                if type(tag) is Tag:
                    code = self.read_text_in(tag.fname) or ""

                    context = TreeContext(
                        tag.rel_fname,
                        code,
                        color=False,
                        line_number=False,
                        child_context=False,
                        last_line=False,
                        margin=0,
                        mark_lois=False,
                        loi_pad=0,
                        # header_max=30,
                        show_top_of_file_parent_scope=False,
                    )
                cur_fname = this_rel_fname

            if context:
                context.add_lines_of_interest([tag.line])

        return output