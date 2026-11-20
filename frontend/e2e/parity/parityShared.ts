import { closeSync, existsSync, mkdirSync, openSync, readFileSync, renameSync, unlinkSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const WAIT_MS = 10 * 60_000;
const POLL_MS = 2000;

function held<T>(file: string): T | null {
  return existsSync(file) ? (JSON.parse(readFileSync(file, "utf8")) as T) : null;
}

function claimed(lock: string): boolean {
  try {
    closeSync(openSync(lock, "wx"));
    return true;
  } catch {
    return false;
  }
}

async function made<T>(file: string, lock: string, make: () => Promise<T>): Promise<T> {
  try {
    const value = await make();
    writeFileSync(`${file}.part`, JSON.stringify(value));
    renameSync(`${file}.part`, file);
    return value;
  } catch (error) {
    unlinkSync(lock);
    throw error;
  }
}

export async function sharedOnce<T>(folder: string, name: string, make: () => Promise<T>): Promise<T> {
  mkdirSync(folder, { recursive: true });
  const file = join(folder, `${name}.json`);
  const lock = join(folder, `${name}.lock`);
  const ready = held<T>(file);
  if (ready !== null) return ready;
  if (claimed(lock)) return made(file, lock, make);
  for (const start = Date.now(); Date.now() - start < WAIT_MS; ) {
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
    const found = held<T>(file);
    if (found !== null) return found;
    if (!existsSync(lock) && claimed(lock)) return made(file, lock, make);
  }
  return make();
}
