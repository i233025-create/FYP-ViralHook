// ViralHook logo: the hook mark (from ui_demo) + a Bebas Neue wordmark.
import { useId } from 'react'

export function LogoMark({ className = 'h-8 w-auto text-vh-accent', title = 'ViralHook' }) {
  const maskId = `vh-logo-${useId().replace(/:/g, '')}`
  return (
    <svg viewBox="20 10 202 356" className={`overflow-visible ${className}`} role="img" aria-label={title}>
      <g transform="translate(16.000 16.000) scale(1.60566) translate(-6 60)">
<mask id={maskId} maskUnits="userSpaceOnUse" x="-100" y="-200" width="400" height="500"><rect x="-100" y="-200" width="400" height="500" fill="#fff"/><path d="M94.47 16.44 L98 8.49 M96.48 17.33 L100.01 9.38 M98.5 18.23 L102.03 10.28 M100.51 19.12 L104.04 11.17" fill="none" stroke="#000" strokeWidth="4.2" strokeLinecap="round"/></mask>
<path d="M101.02 9.83 L129.68 -54.7" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
<g mask={`url(#${maskId})`}>
<path d="M92.15 29.8 L39.3 148.9 L18.1 110 A18.05 18.05 0 0 1 34 83.3" fill="none" stroke="currentColor" strokeWidth="11.4" strokeLinecap="round" strokeLinejoin="round"/>
<polygon points="36.8,70.3 58.6,82.3 37.8,96.1" fill="currentColor" stroke="currentColor" strokeWidth="1.6" strokeLinejoin="round"/>
<circle cx="95.7" cy="21.8" r="8.75" fill="none" stroke="currentColor" strokeWidth="6"/>
</g>
<path d="M94.47 16.44 L98 8.49 M96.48 17.33 L100.01 9.38 M98.5 18.23 L102.03 10.28 M100.51 19.12 L104.04 11.17" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round"/>
<path d="M102.4 10.4 Q106.2 10.1 108.4 13.4" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
</g>
    </svg>
  )
}

/**
 * Hook mark + "VIRAL" / "HOOK" wordmark in Bebas Neue, as in the design.
 * tone="dark": on black (VIRAL in cream) · tone="light": on cream (VIRAL in black).
 */
export default function Logo({ size = 'md', tone = 'dark' }) {
  const big = size === 'lg'
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark title="" className={`${big ? 'h-11' : 'h-8'} w-auto text-vh-accent`} />
      <span className={`display leading-none ${big ? 'text-[2.6rem]' : 'text-[1.9rem]'} tracking-[0.01em]`} aria-label="ViralHook">
        <span className={tone === 'dark' ? 'text-vh-cream' : 'text-vh-night'}>Viral</span>
        <span className="text-vh-accent">Hook</span>
      </span>
    </span>
  )
}
