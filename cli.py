from __future__ import annotations
from collections.abc import Iterable
from typing import Optional, Callable, Any
from dataclasses import dataclass, field
from .parsing import deliminate_text_args, extract_positionals_and_kwargs, parse_arguments
from .command import Command
from .errors import CLIError, CommandNotFoundError, EmptyEntryError


class CLI:
    '''Command-Line Interface'''

    # Attribute applied to function to know what CLIs its part of
    CLI_ATTR = '__cli__'

    # Attribute applied to fuction to know which CLI invoked it
    INVOKER_ATTR = '__invoker__'

    def __init__(self, title: str, entry_marker: Optional[str] = None, arg_parsers: Optional[dict[type, Callable]] = None, commands: Optional[list[Command]] = None, ignore_case: Optional[bool] = False, env_vars: Optional[dict[str, Any]] = None) -> None:
        self.title: str = title
        self.entry_marker: str = '>' if entry_marker is None else entry_marker
        self.arg_parsers: dict[type, Callable] = {} \
            if arg_parsers is None else arg_parsers
        self._commands: list[Command] = [] if commands is None else commands
        self.ignore_case = ignore_case
        self._keep_running: bool = False
        self.env_vars = {} if env_vars is None else env_vars
        self._invoking_func = None
        self._invoking = None

    def commands(self) -> list[Command]:
        '''Get all commands'''

        return self._commands

    def add_command(self, func_or_cmd: Callable | Command, matches: Optional[tuple[str]] = None, detail: Optional[str] = None, verb: Optional[Verb] = None, options: Optional[dict[str, Any]] = None) -> None:
        '''Adds command this CLI, `func_or_cmd` can be a function or Command'''

        def set_cli(func):
            if not hasattr(func, CLI.CLI_ATTR):
                setattr(func, CLI.CLI_ATTR, [self])
            else:
                func.__cli__.append(self)
            if not hasattr(func, CLI.INVOKER_ATTR):
                setattr(func, CLI.INVOKER_ATTR, None)

        if isinstance(func_or_cmd, Command):
            if not all(arg is None for arg in [matches, detail, verb, options]):
                raise RuntimeError(
                    f'{self.add_command.__name__}(...), when {func_or_cmd} is of type {Command.__name__}, all other args must be None')
            self._commands.append(func_or_cmd)
            set_cli(func_or_cmd.function)
        else:
            options = dict() if options is None else options
            set_cli(func_or_cmd)
            self._commands.append(
                Command(func_or_cmd, matches, detail, verb, options))

    def command(self, matches: Optional[tuple[str]] = None, detail: Optional[str] = None, verb: Optional[Verb] = None, options: Optional[dict[str, Any]] = None) -> Callable[[Callable], Callable]:
        '''Add decorated function to this CLI'''

        def decorator(func: Callable) -> Callable:
            self.add_command(func, matches, detail, verb, options)
            return func
        return decorator

    def match_command(self, command_name: str) -> Command | None:
        matches: Iterable[Command] = filter(
            lambda cmd: command_name in ([match.lower() for match in cmd.matches] if self.ignore_case else cmd.matches), \
                self._commands)
        try:
            matched: Command = next(matches)
        except StopIteration as e:
            raise CommandNotFoundError(
                f'Command {command_name} not found') from e

        try:
            other: Command = next(matches)
        except StopIteration:
            return matched
        else:
            raise RuntimeError(
                f'{command_name} matched two commands -> {matched} and {other}')

    def execute(self, line_or_entries: str | Iterable[str]) -> tuple[Command, Any]:
        '''Execute one command with given line or entries'''

        extractor: Callable[[str | Iterable[str]], tuple[list[str], dict[str, str]]] = \
            deliminate_text_args if isinstance(line_or_entries, str) else extract_positionals_and_kwargs
        args, kwargs = extractor(line_or_entries)

        if len(args) == 0:
            raise EmptyEntryError('Nothing was entered')

        command_name: str = args[0]
        args: list[str] = args[1:]

        if self.ignore_case:
            command_name = command_name.lower()

        matched = self.match_command(command_name)

        self._invoking = matched
        self._invoking_func = matched.function
        matched.function.__invoker__ = self

        parsed_args, parsed_kwargs = parse_arguments(
            args, \
            kwargs, \
            matched.positional_types(), \
            matched.kwarg_types(), matched.has_var_args(), \
            matched.has_var_kwargs(), self.arg_parsers)

        results = matched, matched.function(*parsed_args, **parsed_kwargs)

        matched.function.__invoker__ = None
        self._invoking_func = None
        self._invoking = None

        return results

    def run(self, exception_handler: Optional[Callable[[Exception], None]] = None, return_value_handler: Optional[Callable[[Command, Any], None]] = None) -> None:
        '''Loop execute() until stop() is called'''

        def with_except():
            try:
                results: tuple[Command, Any] = self.execute(
                    input(f'{self.title}{self.entry_marker}'))
            except Exception as e:
                exception_handler(e)
                if self._invoking_func:
                    self._invoking_func.__invoker__ = None
                self._invoking_func = None
                self._invoking = None
            else:
                if return_value_handler is not None:
                    return_value_handler(*results)

        def without_except():
            try:
                results: tuple[Command, Any] = self.execute(
                    input(f'{self.title}{self.entry_marker}'))
            except CLIError as e:
                if self._invoking_func:
                    self._invoking_func.__invoker__ = None
                self._invoking_func = None
                self._invoking = None
                print(f'An error occured: {repr(e)}')
            else:
                if return_value_handler is not None:
                    return_value_handler(*results)

        executor: Callable[[]] = \
            without_except if exception_handler is None else with_except

        self._keep_running = True
        while self._keep_running:
            executor()

    def invoking(self) -> Command | None:
        '''Get which command is getting invoked'''
        return self._invoking

    def stop(self) -> None:
        '''Stop loop in run()'''

        self._keep_running = False


@dataclass
class Verb:
    '''All data relating to Verb-Noun pattern for commands'''

    cli:                    CLI
    verb:                   str
    verb_noun_delimiter:    str = field(default_factory=lambda: '-')
    keep_original_matches:  bool = field(default=True)
    remove_verb_from_func:  bool = field(default=True)
    options:                dict[str, Any] = field(default_factory=dict)

    def noun(self, matches: Optional[tuple[str]] = None, detail: Optional[str] = None, options: Optional[dict[str, Any]] = None) -> Callable[[Callable], Callable]:
        '''Add decorated function to `cli` and apply verb-noun options'''

        return self.cli.command(matches, detail, self, options)


def cli_of(func) -> list[CLI]:
    '''Get what CLIs `func` is part of'''

    if not hasattr(func, CLI.CLI_ATTR):
        return []
    return func.__cli__


def invoker(func) -> CLI | None:
    '''Get what CLI invoked `func`. If none, was not invoked by CLI'''

    if not hasattr(func, CLI.INVOKER_ATTR):
        return None
    return func.__invoker__
