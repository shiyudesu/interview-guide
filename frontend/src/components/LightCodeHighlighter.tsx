import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import type { SyntaxHighlighterProps } from 'react-syntax-highlighter';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import c from 'react-syntax-highlighter/dist/esm/languages/prism/c';
import cpp from 'react-syntax-highlighter/dist/esm/languages/prism/cpp';
import csharp from 'react-syntax-highlighter/dist/esm/languages/prism/csharp';
import docker from 'react-syntax-highlighter/dist/esm/languages/prism/docker';
import go from 'react-syntax-highlighter/dist/esm/languages/prism/go';
import java from 'react-syntax-highlighter/dist/esm/languages/prism/java';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import markdown from 'react-syntax-highlighter/dist/esm/languages/prism/markdown';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import rust from 'react-syntax-highlighter/dist/esm/languages/prism/rust';
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import yaml from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';

for (const [name, grammar] of Object.entries({
  bash,
  c,
  cpp,
  csharp,
  docker,
  go,
  java,
  javascript,
  json,
  markdown,
  python,
  rust,
  sql,
  typescript,
  yaml,
})) {
  SyntaxHighlighter.registerLanguage(name, grammar);
}

SyntaxHighlighter.alias('bash', ['sh', 'shell', 'zsh']);
SyntaxHighlighter.alias('csharp', ['cs', 'dotnet']);
SyntaxHighlighter.alias('docker', 'dockerfile');
SyntaxHighlighter.alias('javascript', ['js', 'jsx']);
SyntaxHighlighter.alias('markdown', ['md', 'mdown']);
SyntaxHighlighter.alias('typescript', ['ts', 'tsx']);
SyntaxHighlighter.alias('yaml', 'yml');

export default function LightCodeHighlighter(props: SyntaxHighlighterProps) {
  return <SyntaxHighlighter {...props} />;
}
