'''
    This module contains all parsing function to make CLI work
'''

import builtins
import codecs
from typing import Callable, Any, Optional, get_args
from itertools import zip_longest
from collections.abc import Iterable
from .errors import ArgumentTypeError, TooManyArgumentsError, NotEnoughPositionalArgumentsError, UnescapedSequenceError, NotAKeywordError, KeywordAlreadyGivenError


def from_type_annotation(annotation: str) -> type | None:
    '''Get type from type annotation "str" -> str, str -> str'''

    args = get_args(annotation)
    if args:
        annotation = args[0]

    if isinstance(annotation, type):
        return annotation

    try:
        return getattr(builtins, annotation)
    except AttributeError:
        try:
            t = globals()[annotation]
        except KeyError:
            return None
        return t if isinstance(t, type) else None


def split_outside_of(text: str, string_escape='\'"', do_not_escape_char: str = '\\') -> list[str]:
    '''Split words except sentences identified by "" or ''. Use \' or \" to insert it into sentence'''

    text = text.strip()
    split: list[str] = ['']

    do_not_escape = False
    esacpe_char = None
    for i, c in enumerate(text):
        if c in string_escape:
            if esacpe_char is None:
                esacpe_char = c
            elif do_not_escape:
                split[-1] += c
                do_not_escape = False
            elif esacpe_char == c:
                esacpe_char = None
            continue

        if esacpe_char is None and c == ' ':
            if split[-1] != '':  # Add next split if last c wasn't also a whitespace
                split.append('')
            continue
        elif esacpe_char is not None and c == do_not_escape_char and not do_not_escape:
            do_not_escape = True
            continue
        do_not_escape = False
        split[-1] += c

    if esacpe_char is not None:
        raise UnescapedSequenceError(
            f'Escaped with {esacpe_char} but was not closed')
    if len(split) == 1 and not split[0]:
        return []
    return split


def extract_positionals_and_kwargs(entries: Iterable[str], equality_specifier='=', string_escape='\'"') -> dict[str, str]:
    '''Extract positionals and keywords from `entries` given the `equality_specifier`'''

    positionals: list[str] = []
    kwargs: dict[str, str] = {}
    escape_char: str | None = None
    keyword: str | None = None
    next_is_value: bool = False

    for index, arg in enumerate(entries):
        if next_is_value:
            if not arg:
                continue

            if keyword is None:
                raise RuntimeError(
                    'Unexpected result, keyword should not be None when next_is_value')
            kwargs[keyword] = arg
            next_is_value = False
            continue

        if escape_char is not None:  # Escaped
            if arg.endswith(escape_char):  # End escape
                if arg != escape_char and positionals:  # Somthing to add
                    positionals[-1] += arg[:-1]
                escape_char = None
            else:
                # If arg is empty, its just a whitespace
                positionals[-1] += (arg if arg else '') + ' '
            continue
        # Check each char and if escaped
        escaped: tuple[tuple[str, bool]] | bool = ((c, arg.startswith(c))
                                                   for c in string_escape)

        for c, starts in escaped:
            if not starts:
                continue
            escape_char = c
            escaped = True
            break
        else:
            escaped = False
        # `escape` now tells if this argument escapes

        if escaped:
            if arg == escape_char:
                positionals.append(' ')
            else:
                positionals.append(arg[1:])
                if arg.endswith(escape_char):
                    positionals[-1] = positionals[-1][:-1]
                    escape_char = None  # Escaped and De-escaped
                else:
                    positionals[-1] += ' '
            continue

        if not arg:
            continue

        if arg == equality_specifier:  # Whitespace on either side of kwarg
            # Equality specifier is not first or last argument
            if positionals or index == len(positionals) - 1:
                keyword = positionals.pop()
                next_is_value = True
                continue

        if arg.endswith(equality_specifier):
            if index != len(positionals) - 1:  # Equality specifier is not very last
                keyword = arg[:-1*len(equality_specifier)]
                next_is_value = True
                continue

        if equality_specifier in arg:
            # If it starts, assume its a positional since no keyword is given
            if not arg.startswith(equality_specifier):
                center = arg.index(equality_specifier)
                kwargs[arg[:center]] = arg[center + len(equality_specifier):]
                continue

        positionals.append(arg)

    if escape_char is not None:
        raise UnescapedSequenceError(
            f'Escaped with {escape_char} but was not closed')
    if next_is_value:
        raise UnescapedSequenceError(
            f'Keyword {keyword} was not given a value')
    return positionals, kwargs


def deliminate_text_args(line: str, equality_specifier='=', string_escape='\'"') -> tuple[list[str], dict[str, str]]:
    '''Extract positionals and keywords from the `line` given the `equality_specifier`'''

    return extract_positionals_and_kwargs(split_outside_of(line), equality_specifier, string_escape)


def parse_arguments(args: list[str], kwargs: dict[str, str], positionals: list[type], keywords: list[dict[str, type]], var_args: bool, var_kwargs: bool, parsers: Optional[dict[type, Callable]] = None) -> tuple[list[Any], dict[str, Any]]:
    '''
        KEWORD_ONLY kind parameters are not supported
        `args` (Entered): list[str] -> ['arg1', 'arg 2'...] 
        `kwargs` (Entered): dict[str, str] -> { 'kwarg1': 'val', 'kwarg2': 'val'... }
        `positionals` (Required arguments): list[type] -> [str, str, int...]
        `keywords` (Optional arguments): list[dict[str, type]] -> [{'count': int, 'filename': str... }...]
        `var_args`: bool -> Has `(*)` ex. `func(*args)` all var args will be parsed as str
        `var_kwargs`: bool -> Has `(**)` ex. `func(**kwargs)` all var kwargs will be parsed as str
        `parsers`: Optional[dict[type, Callable]] -> A string to instance converter -> { my_type: str_to_my_type... }
    '''
    if parsers is None:
        parsers = {}

    if not var_args:
        total_defined_args_count = len(args) + len(kwargs)
        if len(args) > total_defined_args_count:
            raise TooManyArgumentsError(
                f'Supplied {len(args)} but max (positionals and keywords) is {total_defined_args_count}')
    if not var_kwargs and len(kwargs) > len(keywords):
        raise TooManyArgumentsError(
            f'Supplied {len(args)} keywords but only {len(positionals)} is allowed')

    parsed_postitionals: list[Any] = []
    parsed_keywords: dict[str, Any] = {}

    def parse_positionals_and_positional_keywords():
        for entered_arg_pos, (arg, positional_type) in enumerate(zip_longest(args, positionals)):
            parsed = None
            past_positionals_to_keywords = positional_type is None and not var_args

            if past_positionals_to_keywords:
                # Calculate keyword positional position
                keyword, arg_type = \
                    keywords[entered_arg_pos - len(positionals)]

                def appender(): parsed_keywords[keyword] = parsed
            else:
                if positional_type is not None:  # Still in defined positionals
                    arg_type = positional_type
                else:  # In var args
                    arg_type = str

                def appender(): parsed_postitionals.append(parsed)

            parser = parsers[arg_type] if arg_type in parsers else arg_type
            try:
                parsed = parser(arg)
            except Exception as e:
                raise ArgumentTypeError(
                    f'Could not parse {arg} in position {entered_arg_pos} as {arg_type}{f" for {keyword}" if past_positionals_to_keywords else ""}') from e
            else:
                appender()

    def parse_only_keywords():
        if not var_kwargs and len(parsed_keywords) == len(keywords):  # All done
            return

        for keyword, arg in kwargs.items():
            if keyword in parsed_keywords:
                raise TooManyArgumentsError(
                    f'Keyword {keyword} was given twice either as a keyword or most probably, a positional')

            try:
                _, arg_type = \
                    next(filter(lambda tup: tup[0] == keyword, keywords))
                parser = parsers[arg_type] if arg_type in parsers else arg_type
            except StopIteration as e:
                if not var_args:
                    raise TooManyArgumentsError(
                        f'Keyword {keyword} is not a keyword argument') from e
                else:
                    arg_type = str
                    parser = str

            try:
                parsed = parser(arg)
            except Exception as e:
                raise ArgumentTypeError(
                    f'Could not parse {arg} as {arg_type} for {keyword}') from e
            else:
                parsed_keywords[keyword] = parsed

    parse_positionals_and_positional_keywords()
    parse_only_keywords()

    return parsed_postitionals, parsed_keywords


def process_escape_characters(string: str, custom_escape_encoding: Optional[str] = None) -> str:
    '''Process escape characters for what the user entered'''

    if custom_escape_encoding is None:
        custom_escape_encoding = 'unicode_escape'
    return codecs.getdecoder(custom_escape_encoding)(string)[0]
