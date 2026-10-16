// The site's database client (@libsql/client, Node) against the NEW databases: which calls work? (16 Oct 2026: the site
// got "HTTP status 400" from the new Mumbai databases while the Python tools worked.) Read-only.
import { createClient } from '@libsql/client'
const which = process.argv[2]
const ver = process.argv[3] || '?'
for (const [label, prefix] of [['NEW', 'NEW_'], ['OLD', 'SATYA_']]) {
  const url = process.env[`${prefix}${which.toUpperCase()}_DB_URL`].trim().replace('turso://', 'libsql://')
  const c = createClient({ url, authToken: process.env[`${prefix}${which.toUpperCase()}_DB_TOKEN`].trim() })
  const tests = [
    ['execute SELECT 1', () => c.execute('SELECT 1 AS x')],
    ['execute with args', () => c.execute({ sql: 'SELECT ? AS x', args: [5] })],
    ['table read', () => c.execute(which === 'upsc' ? 'SELECT article_id FROM upsc_articles ORDER BY article_id DESC LIMIT 3' : 'SELECT article_id FROM upsc_translations ORDER BY article_id DESC LIMIT 3')],
    ['batch (default)', () => c.batch(['SELECT 1', 'SELECT 2'])],
    ['batch read', () => c.batch(['SELECT 1', 'SELECT 2'], 'read')],
  ]
  for (const [name, f] of tests) {
    try { const r = await f(); console.log(`| ${ver} | ${label} | ${name} | ok | ${JSON.stringify(Array.isArray(r) ? r.map(x => x.rows) : r.rows).slice(0, 80)} |`) }
    catch (e) { console.log(`| ${ver} | ${label} | ${name} | FAILED | ${String(e?.message).slice(0, 160)} ${String(e?.cause?.message ?? '').slice(0, 120)} |`) }
  }
  c.close()
}
