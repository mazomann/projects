import pg from "pg";
import { SQL, type QueryName } from "./queries.js";

// NUMERIC comes back as a string by default so precision is never lost; the dashboard formats it, it never does math on it.
const DEFAULT_URL = "postgresql://postgres:postgres@localhost:5432/automations";

export interface Db {
  run<T = Record<string, unknown>>(name: QueryName, params?: unknown[]): Promise<T[]>;
  close(): Promise<void>;
}

export function makeDb(): Db {
  const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL ?? DEFAULT_URL, max: 4 });
  return {
    async run(name, params = []) {
      const { rows } = await pool.query(SQL[name], params);
      return rows;
    },
    close: () => pool.end(),
  };
}
