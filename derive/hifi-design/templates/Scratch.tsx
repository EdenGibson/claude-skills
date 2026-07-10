'use client';

import { Function } from '@phosphor-icons/react';

/**
 * hifi-design scratch surface — edit freely. Same rules as the app:
 *   • colour / spacing / radius / shadow → var(--token), never a raw hex
 *   • icons → @phosphor-icons/react (bold by default via the app's PhosphorIconProvider)
 * Keeping to those rules is what makes graduating this into a real component a copy-paste.
 * Replace everything below with the component you're designing.
 */
export default function Scratch() {
  return (
    <div style={{ maxWidth: 720, margin: '0 auto', padding: 'var(--space-8) var(--space-5)' }}>
      <div
        style={{
          display: 'inline-grid',
          placeItems: 'center',
          width: 44,
          height: 44,
          borderRadius: 'var(--radius-md)',
          background: 'var(--color-primary-faint)',
          color: 'var(--color-primary)',
          marginBottom: 'var(--space-4)',
        }}
      >
        <Function size={24} />
      </div>

      <h1
        style={{
          fontSize: 'var(--text-xl)',
          letterSpacing: '-0.01em',
          marginBottom: 'var(--space-2)',
        }}
      >
        Scratch surface
      </h1>

      <p style={{ color: 'var(--color-text-secondary)', marginBottom: 'var(--space-6)' }}>
        Real tokens, real four themes, real Phosphor — what you see is what ships. Edit{' '}
        <code style={{ fontFamily: 'var(--font-mono)' }}>Scratch.tsx</code> and it hot-reloads on
        your laptop. Flip the themes above to prove the design across all four.
      </p>

      <button
        type="button"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: 'var(--space-2)',
          padding: '9px 16px',
          borderRadius: 'var(--radius-md)',
          background: 'var(--color-surface-1)',
          color: 'var(--color-text-primary)',
          border: '1px solid var(--color-border)',
          boxShadow: 'var(--shadow-1)',
          fontSize: 'var(--text-sm)',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        Example button
      </button>
    </div>
  );
}
