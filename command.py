'''
    Command class file
'''

from __future__ import annotations
from inspect import signature, Signature, Parameter
from typing import Callable
from dataclasses import dataclass, field
from .parsing import from_type_annotation


@dataclass
class Command:
    '''All data relating to  a command'''

    # Attribute applied to function to list all commands of the function
    CMD_ATTR = '__cmd__'

    function:   Callable
    matches:    tuple[str]              = field(default_factory=lambda: None)
    detail:     str                     = field(default_factory='')
    verb:       Verb | None             = field(default_factory=lambda: None)
    options:    dict[str, Any] | None   = field(default_factory=lambda: {})

    def __post_init__(self) -> None:
        self._signature: Signature = signature(self.function)

        self._positionals: list[Parameter] = list(filter(
            lambda param: param.default is param.empty and param.kind == param.POSITIONAL_OR_KEYWORD, \
                self._signature.parameters.values()))
        self._keywords: list[Parameter] = list(filter(
            lambda param: param.default is not param.empty, \
                self._signature.parameters.values()))

        assert all(param.kind != param.KEYWORD_ONLY for param in self._signature.parameters.values()), \
            'KEYWORD_ONLY kinds parameters are not supported by parsing.parse_arguments'

        self._positional_types: list[type] = [str if param.annotation is None else from_type_annotation(param.annotation) \
                                              for param in self._positionals]
        self._kwarg_types: list[tuple[str, type]] = [(param.name, str if param.annotation is None else from_type_annotation(param.annotation)) \
                                                     for param in self._keywords]
        self.options = {} if self.options is None else self.options

        if not hasattr(self.function, Command.CMD_ATTR):
            setattr(self.function, Command.CMD_ATTR, [self])
        else:
            self.function.__cmd__.append(self)

        if self.matches is None or not self.matches:
            self.matches = ()
            self.generate_matches()
        elif self.verb is not None and not self.verb.keep_original_matches:
            self.generate_matches()

        if self.detail is None or not self.detail:
            self.generate_detail()

    def generate_detail(self) -> None:
        '''Automatically generate `detail` from function signature'''

        self.detail = ''

        for index, match in enumerate(self.matches):
            self.detail += match
            if index != len(self.matches) - 1:
                self.detail += ', '

        if not self._positionals and not self._keywords:
            return

        self.detail += ': '

        for index, param in enumerate(self._positionals):
            self.detail += f'<{param.name}: {"str" if param.annotation is None else from_type_annotation(param.annotation).__name__}>'
            if index != len(self._positionals) - 1:
                self.detail += ' '

        if len(self._keywords) != 0 and self.detail[-1] != ' ':
            self.detail += ' '

        for index, param in enumerate(self._keywords):
            self.detail += f'<{param.name}? = {param.default}: {"str" if param.annotation is None else from_type_annotation(param.annotation).__name__}>'
            if index != len(self._keywords) - 1:
                self.detail += ' '

        if self.has_var_args():
            self.detail += ' <*args>'
        if self.has_var_kwargs():
            self.detail += ' <**kwargs>'

    def generate_matches(self) -> None:
        '''Automatically generate matches based on function name and `verb` if not None'''

        if self.verb is None:
            self.matches = tuple([self.function.__name__])
            return

        if not self.verb.keep_original_matches:
            self.matches = ()

        verb_match = self.function.__name__
        if self.verb.remove_verb_from_func:
            verb_match = verb_match.replace(self.verb.verb, '')
            while verb_match.startswith('_'):
                verb_match = verb_match[1:]
            verb_match = f'{self.verb.verb}{self.verb.verb_noun_delimiter}{verb_match}'
        self.matches = tuple([verb_match]) + self.matches

    def has_var_kwargs(self) -> bool:
        '''Function has `**kwargs`'''

        return any(param.kind == Parameter.VAR_KEYWORD \
                   for param in self._signature.parameters.values())

    def has_var_args(self) -> bool:
        '''Function has *args'''

        return any(param.kind == Parameter.VAR_POSITIONAL \
                   for param in self._signature.parameters.values())

    def positional_types(self) -> list[type]:
        '''Positional types'''

        return self._positional_types

    def kwarg_types(self) -> list[tuple[str, type]]:
        '''Keyword types'''

        return self._kwarg_types


def cmd(cli: CLI, func: Callable) -> Command | None:
    if not hasattr(func, Command.CMD_ATTR):
        return None
    for cmd in func.__cmd__:
        if cmd in cli.commands():
            return cmd
    return None


def cmds(func: Callable) -> list[Command] | None:
    '''Get all commands `func` is a part of'''

    if not hasattr(func, Command.CMD_ATTR):
        return None
    return func.__cmd__
