// Deterministic display-only tokenizer for CodeBlock. It classifies text into
// keyword/string/comment/number/punctuation/plain spans; nothing is evaluated.
const KEYWORDS = {
  python:
    "def class return if elif else for while in not and or import from as with try except finally raise lambda yield pass break continue None True False async await global nonlocal is del assert",
  typescript:
    "const let var function return if else for while do switch case break continue new class extends implements interface type import export from as default async await try catch finally throw this null undefined true false typeof instanceof in of enum public private protected readonly static void never any unknown string number boolean",
  javascript:
    "const let var function return if else for while do switch case break continue new class extends import export from as default async await try catch finally throw this null undefined true false typeof instanceof in of static void",
  go: "package import func return if else for range switch case break continue type struct interface map chan go defer select var const nil true false make new len append error",
  rust: "fn let mut pub struct enum impl trait for in if else match return use mod crate self Some None Ok Err loop while break continue as where dyn ref move async await unsafe type const static true false",
  bash: "if then else elif fi for while do done case esac function return export local echo exit in",
  sql: "select from where insert into values update set delete join left right inner outer on group by order having limit offset as and or not null is create table primary key index drop alter add distinct count sum avg min max union all case when then else end",
  yaml: "true false null",
  json: "true false null",
  c: "int char float double void return if else for while do switch case break continue struct typedef enum const static unsigned signed long short sizeof include define NULL",
  cpp: "int char float double void return if else for while do switch case break continue struct class typedef enum const static unsigned signed long short sizeof include define nullptr auto template typename namespace using public private protected virtual override new delete this true false bool",
  java: "int char float double void return if else for while do switch case break continue class interface extends implements import package public private protected static final new this null true false boolean String abstract throws try catch finally throw",
  text: "",
};

const COMMENT = {
  python: "#",
  bash: "#",
  yaml: "#",
  sql: "--",
  typescript: "//",
  javascript: "//",
  go: "//",
  rust: "//",
  c: "//",
  cpp: "//",
  java: "//",
  json: null,
  text: null,
};

const TOKEN = /(\s+)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\.|[^`\\])*`)|(\b\d+(?:\.\d+)?\b)|([A-Za-z_][A-Za-z0-9_]*)|(.)/g;

export const LANGUAGES = Object.keys(KEYWORDS);

export const tokenize = (line, language = "text") => {
  const words = new Set((KEYWORDS[language] || "").split(" ").filter(Boolean));
  const comment = COMMENT[language];
  const tokens = [];
  const cut = comment ? line.indexOf(comment) : -1;
  const code = cut >= 0 ? line.slice(0, cut) : line;
  TOKEN.lastIndex = 0;
  let match;
  while ((match = TOKEN.exec(code))) {
    const [text, space, string, number, ident, punct] = match;
    if (space) tokens.push({ type: "plain", text });
    else if (string) tokens.push({ type: "string", text });
    else if (number) tokens.push({ type: "number", text });
    else if (ident)
      tokens.push({
        type: words.has(language === "sql" ? text.toLowerCase() : text)
          ? "keyword"
          : "plain",
        text,
      });
    else tokens.push({ type: /[A-Za-z0-9\s]/.test(punct) ? "plain" : "punctuation", text });
  }
  if (cut >= 0) tokens.push({ type: "comment", text: line.slice(cut) });
  return tokens;
};
