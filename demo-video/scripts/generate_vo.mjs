// Generate the voiceover with ElevenLabs and write a timing manifest.
// Reads ELEVENLABS_API_KEY from ../.env (repo root) or the environment.
// Usage: node scripts/generate_vo.mjs
import { execSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..');

function loadKey() {
  if (process.env.ELEVENLABS_API_KEY) return process.env.ELEVENLABS_API_KEY.trim();
  const envPath = path.join(root, '..', '.env');
  if (fs.existsSync(envPath)) {
    const m = fs.readFileSync(envPath, 'utf8').match(/^ELEVENLABS_API_KEY\s*=\s*(.+)$/m);
    if (m) return m[1].trim().replace(/^["']|["']$/g, '').split('#')[0].trim();
  }
  throw new Error('ELEVENLABS_API_KEY not found (env or repo-root .env)');
}

const KEY = loadKey();
const VOICE = process.env.ELEVEN_VOICE_ID || 'nPczCjzI2devNBz1zQrb'; // Brian — deep narrator
const MODEL = 'eleven_multilingual_v2';

const { scenes } = JSON.parse(fs.readFileSync(path.join(here, 'vo-script.json'), 'utf8'));
const outDir = path.join(root, 'public', 'audio');
fs.mkdirSync(outDir, { recursive: true });

function probeSeconds(file) {
  const out = execSync(`afinfo "${file}"`).toString();
  const m = out.match(/estimated duration:\s*([\d.]+)/);
  if (!m) throw new Error(`no duration for ${file}`);
  return parseFloat(m[1]);
}

const manifest = {};
for (const s of scenes) {
  const dest = path.join(outDir, `${s.id}.mp3`);
  process.stdout.write(`TTS ${s.id} ... `);
  const res = await fetch(
    `https://api.elevenlabs.io/v1/text-to-speech/${VOICE}?output_format=mp3_44100_128`,
    {
      method: 'POST',
      headers: { 'xi-api-key': KEY, 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text: s.text,
        model_id: MODEL,
        voice_settings: { stability: 0.5, similarity_boost: 0.75, style: 0.2, use_speaker_boost: true },
      }),
    },
  );
  if (!res.ok) throw new Error(`${s.id}: HTTP ${res.status} ${await res.text()}`);
  fs.writeFileSync(dest, Buffer.from(await res.arrayBuffer()));
  const dur = probeSeconds(dest);
  manifest[s.id] = Math.round(dur * 100) / 100;
  console.log(`${manifest[s.id]}s`);
}

fs.writeFileSync(path.join(root, 'src', 'audio-manifest.json'), JSON.stringify(manifest, null, 2));
console.log('\nwrote src/audio-manifest.json:', manifest);
