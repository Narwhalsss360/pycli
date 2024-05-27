# PyCLI
# Parameter Kinds

| Enum (_ParameterKind) | Full Word (Documentation) | Explanation (Interpretation)
| --------------------- | ------------------------- | -----------------------------------------
| POSITIONAL_ONLY       | 'positional-only'         | Only pssible for built-ins
| POSITIONAL_OR_KEYWORD | 'positional or keyword'   | Regular arguments *before* `(*)` or `(**)` ex. `func(x, y, *args, **kwargs)`
| VAR_POSITIONAL        | 'variadic positional'     | Argument that is `(*)` ex. `sum(*nums)`
| KEYWORD_ONLY          | 'keyword-only'            | Argument that *procedes* `(*)` ex. `func(x, *args, kw_only)`
| VAR_KEYWORD           | 'variadic keyword'        | Arguemt that is `(**)` ex. `func(x, y, **kwargs)`
