import { useState } from 'react';

export function Copy({ text }: { text: string }) {
  const [ok, setOk] = useState(false);
  return (
    <button
      className="copy-ico"
      title="Copy"
      onClick={(e) => {
        e.stopPropagation();
        navigator.clipboard.writeText(text);
        setOk(true);
        setTimeout(() => setOk(false), 1200);
      }}
    >
      {ok ? '✓' : '⧉'}
    </button>
  );
}
