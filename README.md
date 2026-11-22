# Ruby Shell Script (`.rss`)

**Ruby Shell Script** is a small programming language that looks and feels
like Ruby, but is built for the job bash/sh usually gets stuck with:
gluing shell commands together, reading/writing environment variables,
looping over command output, and doing it all with real data structures
(arrays, hashes, functions) instead of string-splitting and `[[ ]]` soup.

It ships as a self-contained **tree-walking interpreter written in pure
Python** (no dependencies) — a lexer, a recursive-descent parser, and an
evaluator — plus a CLI (`rssc`) and a REPL.

```ruby
# backup.rss
targets = ["~/Projects", "~/Documents"]

targets.each do |dir|
  puts "Backing up #{dir}..."
  sh("tar -czf #{dir.split("/").last}.tar.gz #{dir}")
  puts "  -> exit status #{last_status()}"
end

puts "Done. #{targets.length} folders backed up."
```

```
$ ./rssc backup.rss
Backing up ~/Projects...
  -> exit status 0
Backing up ~/Documents...
  -> exit status 0
Done. 2 folders backed up.
```

---

## Contents

```
rubyshellscript/
├── rss/                  the interpreter (lexer, parser, evaluator, CLI)
│   ├── lexer.py
│   ├── parser.py
│   ├── ast_nodes.py
│   ├── interpreter.py
│   ├── methods.py        built-in methods for String/Array/Hash/Integer/Range
│   ├── runtime_values.py
│   ├── values.py
│   ├── errors.py
│   └── __main__.py       CLI + REPL entry point
├── rssc                  Linux/macOS launcher: `./rssc script.rss`
├── rssc.bat              Windows launcher: `rssc.bat script.rss`
├── examples/             five annotated example scripts
├── tests/                automated test suite (22 tests, stdlib unittest)
└── README.md             this file
```

## Requirements

- Python 3.9+ (nothing else — the interpreter has zero third-party
  dependencies). The lexer/parser/interpreter are pure Python with no
  OS-specific code, so they run the same way on Linux, macOS and
  **Windows**.

## Running scripts

**Linux / macOS:**

```bash
# as an executable
chmod +x rssc
./rssc examples/01_hello.rss JP

# or via the module (works everywhere, including Windows)
python3 -m rss examples/01_hello.rss JP

# inline one-liner
python3 -m rss -e 'puts 2 ** 10'

# interactive REPL
python3 -m rss
```

**Windows (PowerShell or cmd.exe):**

```powershell
# via the included .bat launcher
rssc.bat examples\01_hello.rss JP

# or via the module (always works, no launcher needed)
python -m rss examples\01_hello.rss JP
python -m rss -e "puts 2 ** 10"
python -m rss
```

Run the test suite with:

```bash
python3 tests/test_interpreter.py     # Linux/macOS
python tests\test_interpreter.py      # Windows
```

### A note on shell commands across platforms

Backticks, `sh()` and `exec()` all run through Python's `subprocess`
with `shell=True`, which means the *interpreter itself* is portable,
but the **command strings you put inside them are not** — on
Linux/macOS they're handed to `/bin/sh`, and on Windows to `cmd.exe`.
`` `ls -1` `` works on Linux/macOS; the Windows equivalent is
`` `dir /b` ``. This mirrors how Ruby's and Python's own `` `cmd` ``/
`os.system` work — the language is cross-platform, the shell
commands you choose to run are whatever the host OS understands.
Likewise, `$HOME` is a real env var on Linux/macOS but doesn't exist
on Windows by default (use `$USERPROFILE` there instead).

---

## Language tour

### Variables & types

```ruby
name = "JP"            # String
age = 29                # Integer
pi = 3.14159             # Float
ok = true                # Boolean (true / false)
nothing = nil             # Nil
list = [1, 2, 3]           # Array
person = {name: "JP", age: 29}  # Hash
window = 1..10              # Range (inclusive)
```

Values are duck-typed, like Ruby: no type declarations.

### Strings

Double-quoted strings interpolate with `#{...}`; single-quoted strings
don't:

```ruby
x = 10
puts "x is #{x}, doubled is #{x * 2}"
puts 'no #{interpolation} here'
```

Useful methods: `.length`, `.upcase`, `.downcase`, `.capitalize`,
`.strip`, `.split(sep)`, `.reverse`, `.include?`, `.start_with?`,
`.end_with?`, `.to_i`, `.to_f`, `.sub(a, b)`, `.gsub(a, b)`, `.chars`,
`.each_char do |c| ... end`.

### Arrays & Hashes

```ruby
nums = [5, 3, 1, 4, 2]
puts nums.sort.inspect                 # [1, 2, 3, 4, 5]
puts nums.select do |n| n > 2 end       # [5, 3, 4]
puts nums.map do |n| n * n end          # [25, 9, 1, 16, 4]
puts nums.reduce(0) do |sum, n| sum + n end  # 15

user = {name: "JP", role: "dev"}
user[:lang] = "rss"            # :symbol literals are shorthand strings
user.each do |k, v|
  puts "#{k} -> #{v}"
end
```

Ranges (`1..10`) support `.each`, `.to_a`, `.sum`, `.include?`, `.min`,
`.max`, and plug directly into `for x in 1..10`.

### Operators

Arithmetic `+ - * / % **`, comparison `== != < > <= >= <=>`, logical
`&& || !` (and their word forms `and or not`), string/array
concatenation with `+`, array difference with `-`, string/array
repetition with `*`. Only `nil` and `false` are falsy — `0` and `""`
are truthy, just like Ruby and unlike most shells.

### Control flow

```ruby
if score > 90
  puts "A"
elsif score > 75
  puts "B"
else
  puts "C"
end

puts "skip" unless allowed

i = 0
while i < 5
  i += 1
end

until done
  step()
end

for item in collection
  puts item
end

loop do
  break if finished?
end

do_thing() if ready       # statement modifiers, Ruby-style
retry_count += 1 while failed?
```

### Functions & blocks

```ruby
def greet(name, greeting = "Hello")
  return "#{greeting}, #{name}!"
end

puts greet("JP")            # Hello, JP!
puts greet("JP", "Hey")      # Hey, JP!

# the last evaluated expression is returned implicitly, Ruby-style
def square(n)
  n * n
end

# do |params| ... end blocks are how iteration/callbacks work
[1, 2, 3].each do |n|
  puts n
end
```

> Function calls always need parentheses, even with zero arguments
> (`foo()`, not `foo`) — this keeps the grammar unambiguous without a
> symbol table pass. `do...end` is the only block syntax (no `{ }`
> blocks yet — see the roadmap).

### Shell integration — the "Shell Script" part

```ruby
# backticks capture stdout as a string, like `cmd` in Ruby/bash
files = `ls -1`.split("\n")

# sh(cmd) runs a command with output streamed live, returns exit code
sh("make build")
puts "exit status: #{last_status()}"

# exec(cmd) replaces the process, like Unix exec() -- never returns
exec("./deploy.sh") if ARGV.include?("--deploy")

# $NAME reads/writes real OS environment variables
puts $HOME
$DEBUG = "1"
sh("./run_with_debug.sh")   # sees DEBUG=1

# ARGV, SCRIPT_NAME, ENV are available like in any scripting language
ARGV.each do |a|
  puts a
end
puts ENV["PATH"]
```

### Error handling

```ruby
begin
  result = risky_operation()
rescue => e
  puts "Something went wrong: #{e}"
ensure
  cleanup()
end
```

### Other built-ins

`puts`, `print`, `p` (inspect + newline), `gets`, `len(x)`, `range(a,b)`,
`rand`, `sleep(s)`, `Integer(x)`, `Float(x)`, `String(x)`, `Array(x)`,
`typeof(x)`, `format(fmt, *args)` / `sprintf`, `exit(code)`,
`block_given?()`, `yield(...)` (calls the block passed to the current
function).

---

## What v0.1 deliberately leaves out

This is a from-scratch language, not a Ruby clone, so some things are
intentionally simplified for now (see the roadmap below for what's
planned):

- No classes/objects yet — `@ivar`s exist as simple script-wide state,
  but there's no `class`/`new`/inheritance.
- `:symbol` literals and the `key:` hash shorthand are just plain
  strings under the hood — there's no distinct, interned Symbol type
  yet (see v0.2 in the roadmap).
- No ternary (`a ? b : c`) and no `case/when`.
- Strings are immutable (no `gsub!`, `<<`, etc.) — reassign instead.
- `if`/`while`/etc. can't be used as the right-hand side of an
  assignment (`x = if ... end` doesn't parse) — only `do...end` blocks
  and function bodies get Ruby's "last expression is the value" rule.
- Only `do...end` blocks — no `{ |x| ... }` brace blocks.
- `require` is parsed but is currently a no-op (no module system yet).

None of this is hidden: scripts that hit an unsupported construct get a
clear parse error pointing at the line and column.

---

## Roadmap — próximas versões

| Version | Theme | Planned features |
|---|---|---|
| **v0.1** *(current)* | Core language | Lexer/parser/interpreter, variables, arrays/hashes/ranges, `if`/`unless`/`while`/`until`/`for`/`loop`, functions with default args, `do...end` blocks & closures, `begin/rescue/ensure`, backticks/`sh()`/`exec()`, `$ENV` variables, REPL. |
| **v0.2** | Syntax completeness | Ternary `? :`, `case/when` pattern matching on values, exclusive ranges `...`, multiple assignment (`a, b = 1, 2`), splat args (`def f(*args)`), `{ \|x\| ... }` brace blocks as a block-syntax alternative, mutable string bang-methods (`upcase!`, `gsub!`, `<<`), a real interned `Symbol` type distinct from `String`. |
| **v0.3** | Real errors | Exception *objects* instead of plain strings (`e.message`, `e.class`), user-defined exception types (`raise "oops"`, `raise ArgumentError.new("bad input")`), `retry` inside `rescue`, better stack traces with full call chains. |
| **v0.4** | Objects | Minimal class system: `class Foo ... end`, `initialize`, instance methods, `attr_accessor`/`attr_reader`, single inheritance (`class Dog < Animal`), `self`. |
| **v0.5** | Modules & stdlib | Working `require`/`require_relative` across `.rss` files, a small standard library wrapping common OS tasks (`File`, `Dir`, `Path`) so simple file scripting doesn't need raw `sh()` calls, `JSON.parse`/`JSON.generate`. |
| **v0.6** | Shell-native sugar | Pipeline syntax for chaining shell commands (`cmd1 \| cmd2`), output redirection sugar (`sh("cmd") > "out.txt"`), background jobs (`spawn`/`wait`), command substitution shortcuts. |
| **v0.7** | Functional bits | `->(x) { x + 1 }` lambda literals, blocks as first-class values (`&block` capture/pass-through), `Proc`/`Lambda` objects with `.call`. |
| **v0.8** | Tooling | `rss fmt` (code formatter), basic linter, syntax-highlighting defs for VS Code/Sublime, a tiny package format for sharing `.rss` libraries. |
| **v0.9** | Performance & polish | Caching/compiling the AST instead of re-parsing on every run, source-snippet error messages with a caret under the exact token, fuzz-tested parser hardening. |
| **v1.0** | Stable release | Locked syntax/semver guarantees, full test coverage of the language reference, `pip install rubyshellscript`, documentation site, and (the real goal) being genuinely pleasant to reach for instead of bash for everyday scripts. |

Contributions and "I wish this language had X" requests are exactly how
this roadmap should evolve — treat it as a living document.

---

## License

MIT — do whatever you want with it. It's a hobby language; have fun.
