import argparse
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence

import libcst as cst

KEY_PATTERN = re.compile(r'^(\"|\')(?P<key>.*)(\"|\')$')
EXIT_CODE_NO_CHANGES = 0
EXIT_CODE_WITH_CHANGES = 1


class Sorting:
    ALPHABETICALY = 'alpha'
    ALL = (ALPHABETICALY,)


def get_formatting(elements: List[cst.CSTNode]):
    return [
        {
            'comma': element.comma,
            'whitespace_after_colon': element.whitespace_after_colon,
            'whitespace_before_colon': element.whitespace_before_colon,
        }
        for element in elements
    ]


def apply_formatting(
    elements: List[cst.CSTNode],
    formatting: List[Dict[str, cst.CSTNode]],
):
    return [
        element.with_changes(**fmt)
        for fmt, element in zip(formatting, elements)
    ]


def extract_key_value(node: cst.BaseString):
    return re.match(KEY_PATTERN, node.value).groupdict()['key']


def get_sorting_func(sorting_type: str):
    return {
        'alpha': lambda x: extract_key_value(x.key),
    }[sorting_type]


def sort_by(elements: List[cst.DictElement], key: Callable):
    # special symbols -> cipher -> uppercase -> lowercase
    return tuple(sorted(elements, key=key))


def ensure_keys_sorted(node: cst.Dict, key: Callable):
    return sort_by(node.elements, key) == node.elements


def ensure_key_not_str(element: cst.Element):
    return not isinstance(element.key, cst.BaseString)


def ensure_starred_element(element: cst.Element):
    return isinstance(element, cst.StarredDictElement)


def ensure_key_formatted_string(element: cst.Element):
    return isinstance(element.key, cst.FormattedString)


def should_transform_dict(
    node: cst.Dict,
    funcs: tuple[Callable] = (
        ensure_starred_element,
        ensure_key_formatted_string,
        ensure_key_not_str,
    ),
) -> bool:
    for element in node.elements:
        for func in funcs:
            if func(element):
                return False
    return True


class DictKeysSorter(cst.CSTTransformer):
    def __init__(self, sorting_type):
        self.transformed = False
        self.sorting_func = get_sorting_func(sorting_type)

    def leave_Dict(self, original_node, updated_node):
        if not should_transform_dict(updated_node):
            return updated_node

        if ensure_keys_sorted(updated_node, self.sorting_func):
            return updated_node

        self.transformed = True

        sorted_elements = apply_formatting(
            elements=sort_by(updated_node.elements, key=self.sorting_func),
            formatting=get_formatting(updated_node.elements),
        )

        return updated_node.with_changes(elements=tuple(sorted_elements))


def ensure_python_file(file_path: Path):
    return file_path.suffix == '.py'


def fix_file(file_path, sorting: str) -> int:
    is_fixed = False

    with file_path.open('r') as file_obj:
        syntax_tree = cst.parse_module(file_obj.read())

    sorter = DictKeysSorter(sorting)
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
        '--sorting',
        type=str,
        choices=[Sorting.ALL],
        default=Sorting.ALPHABETICALY,
        help='Sorting style applied to dictionary keys.',
        action='store',
    )
    args = parser.parse_args(argv)

    return_code = EXIT_CODE_NO_CHANGES

    if not args.filenames:
        return return_code

    for filename in args.filenames:
        file_path = Path(filename)
        if not ensure_python_file(file_path):
            continue

        is_fixed = fix_file(file_path, args.sorting)
        if is_fixed:
            print(f'Fixed {filename}')
            return_code = EXIT_CODE_WITH_CHANGES

    return return_code


if __name__ == '__main__':
    exit(main())
