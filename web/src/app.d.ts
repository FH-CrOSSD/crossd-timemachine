declare global {
  namespace App {}
}
declare module '*.sql?raw' {
  const sql: string;
  export default sql;
}
export {};
