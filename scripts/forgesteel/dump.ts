// Export Forgesteel's core sourcebook (Draw Steel Heroes) as JSON.
//
// Run from inside a Forgesteel checkout, which is where its '@/' imports
// resolve:
//
//   npx tsx --tsconfig tsconfig.json /path/to/this/dump.ts /tmp/core.json
//
// Only the core sourcebook: it is the one covered by the Draw Steel Creator
// License. Forgesteel also carries third-party and community books, which are
// not.
import { core } from '@/data/sourcebooks/official/core';
import { writeFileSync } from 'node:fs';

writeFileSync(process.argv[2] || 'core.json', JSON.stringify(core));
