export type Environment = Record<string, string | undefined>;

export const AZURE_HOST_SUFFIX: string;
export function parseEnvironmentFile(text: string): Record<string, string>;
export function mergeEnvironment(base: Environment, environmentFileText: string): Environment;
export function databaseHost(databaseUrl: string | undefined): string;
export function isAzureHost(host: string): boolean;
export function assertSafeDatabase(environment: Environment): string;
export function preferTestDatabase(environment: Environment): Environment;
export function loadLocalEnvironment(root: string, base?: Environment): Environment;
