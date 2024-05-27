'''
    This file contains all errors that may be raised by this module
'''

from __future__ import annotations
from typing import Optional


class CLIError(Exception):
    '''All errors relating to CLI'''

    def __init__(self, *args: object, command: Optional[Command] = None) -> None:
        super().__init__(*args)
        self.command: Command | None = command


class CommandNotFoundError(CLIError):
    '''Raised when CLI.exec(entries) has an a command name entered that is not a command'''


class EmptyEntryError(CLIError):
    '''Raised when CLI.exec(entries) `entries` is empty'''


class NotEnoughPositionalArgumentsError(CLIError):
    '''Raised when CLI.exec(entries) command argument count specificiation is not met'''


class TooManyArgumentsError(CLIError):
    '''Raised when CLI.exec(entries) command argument count specificiation is not over met'''


class ArgumentTypeError(CLIError):
    '''Raised when CLI.exec(entries) command argument type specificiation is not met'''


class UnescapedSequenceError(CLIError):
    '''Raised when an escaped sequence is not unescaped when extracting positionals and kwargs'''


class NotAKeywordError(CLIError):
    '''Raised when keyword is given that does not exist'''


class KeywordAlreadyGivenError(CLIError):
    '''Raised when a keyword argument is given more than once'''
