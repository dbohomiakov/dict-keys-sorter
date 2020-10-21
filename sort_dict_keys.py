"""

"""

import argparse
import re
from typing import Optional, Dict, Sequence, List
import libcst as cst
from pathlib import Path


KEY_VALUE_PATTERN = re.compile(r'^(\"|\')(?P<key_value>.*)(\"|\')$')
EXIT_CODE_NO_CHANGES = 0
EXIT_CODE_WITH_CHANGES = 1


class Formats:
    KEEP = 'keep'
    ALL = (KEEP,)


def ensure_keys_str(node: cst.Dict):
    return all(
        isinstance(element.key, cst.BaseString)
        for element in node.elements
    )


def get_formatting(elements: List[cst.CSTNode], fmt_type: str):
    if fmt_type == Formats.KEEP:
        formatting = [
            {
                'comma': element.comma,
                'whitespace_before_colon': element.whitespace_before_colon,
                'whitespace_after_colon': element.whitespace_after_colon,
            }
            for element in elements
        ]
    else:
        raise NotImplementedError

    return formatting


def apply_formatting(
    elements: List[cst.CSTNode],
    formatting: List[Dict[str, cst.CSTNode]],
):
    return [
        element.with_changes(**fmt)
        for fmt, element in zip(formatting, elements)
    ]


def extract_key_value(node: cst.BaseString):
    return re.match(
        KEY_VALUE_PATTERN, node.value
    ).groupdict()['key_value']


def sort_by_keys(elements: List[cst.DictElement]):
    # special symbols -> cipher -> uppercase -> lowercase
    return tuple(
        sorted(elements, key=lambda x: extract_key_value(x.key))
    )


def ensure_keys_sorted(node: cst.Dict):
    return sort_by_keys(node.elements) == node.elements


class DictKeysSorter(cst.CSTTransformer):

    def __init__(self, fmt_type):
        self.fmt_type = fmt_type
        self.transformed = False

    def leave_Dict(self, original_node, updated_node):
        if not ensure_keys_str(updated_node):
            return updated_node

        if ensure_keys_sorted(updated_node):
            return updated_node

        self.transformed = True

        sorted_elements = apply_formatting(
            elements=sort_by_keys(updated_node.elements),
            formatting=get_formatting(updated_node.elements, self.fmt_type),
        )

        return updated_node.with_changes(elements=tuple(sorted_elements))


def ensure_python_file(file_path: Path):
    return file_path.suffix == '.py'


def fix_file(file_path, fmt_type: str) -> int:
    is_fixed = False

    with file_path.open('r') as file_obj:
        syntax_tree = cst.parse_module(file_obj.read())

    sorter = DictKeysSorter(fmt_type=fmt_type)
    transformed_tree = syntax_tree.visit(sorter)

    if sorter.transformed:
        with file_path.open('w') as file_obj:
            file_obj.write(transformed_tree.code)
        is_fixed = True

    return is_fixed


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'filenames',
        nargs='*',
        metavar='path',
        type=str,
        help='Filenames to check.',
    )
    parser.add_argument(
        '--fmt_type',
        type=str,
        choices=[Formats.KEEP],
        default=Formats.KEEP,
        help='Format type for dict.',
        action='store',
    )
    args = parser.parse_args(argv)

    return_code = 0

    if not args.filenames:
        return return_code

    for filename in args.filenames:
        file_path = Path(filename)
        if not ensure_python_file(file_path):
            continue

        is_fixed = fix_file(file_path, args.fmt_type)
        if is_fixed:
            print(f'Fixing {filename}')
            return_code = 1

    return return_code


if __name__ == '__main__':
    exit(main())
