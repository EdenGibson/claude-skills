'use client';

import { useEffect, useState } from 'react';
import Scratch from './Scratch';

const THEMES = ['light', 'dark', 'sepia', 'high-contrast'] as const;
type Theme = (typeof THEMES)[number];

/**
 * hifi-design scratch harness — DEV ONLY, never committed (ignored via .git/info/exclude).
 * Stable chrome: a 4-theme switcher that flips `data-theme` for QA, then renders <Scratch/>.
 * Do your design work in Scratch.tsx and leave this file alone.
 */
export default function ScratchPage() {
  const [theme, setTheme] = useState<Theme>('light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
  }, [theme]);

  return (
    <div
      style={{
        minHeight: '100vh',
        background: 'var(--color-background)',
        color: 'var(--color-text-primary)',
        fontFamily: 'var(--font-ui)',
      }}
    >
      <div
        style={{
          position: 'sticky',
          top: 0,
          zIndex: 100,
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-3)',
          padding: 'var(--space-3) var(--space-5)',
          background: 'var(--glass-bg)',
          backdropFilter: 'blur(12px)',
          borderBottom: '1px solid var(--color-divider)',
        }}
      >
        <strong style={{ fontSize: 'var(--text-sm)', letterSpacing: '-0.01em' }}>scratch</strong>
        <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
          hifi-design · dev-only
        </span>
        <div
          role="group"
          aria-label="Theme"
          style={{
            marginLeft: 'auto',
            display: 'inline-flex',
            gap: 2,
            padding: 3,
            background: 'var(--color-surface-2)',
            border: '1px solid var(--color-border)',
            borderRadius: 999,
          }}
        >
          {THEMES.map((t) => {
            const on = t === theme;
            return (
              <button
                key={t}
                type="button"
                aria-pressed={on}
                onClick={() => setTheme(t)}
                style={{
                  border: 0,
                  cursor: 'pointer',
                  padding: '6px 12px',
                  borderRadius: 999,
                  fontSize: 'var(--text-sm)',
                  fontWeight: 500,
                  background: on ? 'var(--color-surface-1)' : 'transparent',
                  color: on ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
                  boxShadow: on ? 'var(--shadow-1)' : 'none',
                }}
              >
                {t}
              </button>
            );
          })}
        </div>
      </div>

      <Scratch />
    </div>
  );
}
