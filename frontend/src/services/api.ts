import axios from 'axios';

// Configure base URL - can be changed based on environment
const API_BASE_URL = 'http://localhost:8000/api';

// Create axios instance with base configuration
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Database types
export interface Connection {
  id?: number;
  name: string;
  description: string;
  db_type: 'mssql' | 'as400' | 'sqlite';
  host: string;
  port: number;
  username: string;
  password: string;
  database?: string;
  database_name?: string;
  status?: string;
}

// Backend returns string[] for schemas, not Schema objects
// Frontend needs to handle this by converting strings to objects
export interface Schema {
  name: string;
}

export interface Table {
  name: string;
  schema: string;
}

export interface TableConfig {
  id?: number;
  table_name: string;
  schema_name: string;
  operation_type: 'all' | 'insert' | 'update' | 'delete';
  operation_delay: number;
  batch_size: number;
  enabled: boolean;
  connection_id: number;
}

export interface PillowFightRequest {
  connection_id: number;
  table_ids: number[];
  operation_type: 'all' | 'insert' | 'update' | 'delete';
  operation_delay: number;
  batch_size: number;
}

export interface PillowFightStatus {
  status: 'idle' | 'running' | 'stopped' | 'error';
  message?: string;
  connection_id?: number;
  table_id?: number;
}

export interface PillowFightStatusResponse {
  pillow_fights: Array<{
    fight_id: string;
    connection_id: number;
    table_id: number;
    table_name: string;
    operation_types: string[];
    operation_delay: number;
    batch_size: number;
    start_time?: string;
    last_operation_time?: string;
    status: string;
    operations: Record<string, any>;
    duration?: number;
  }>;
}

export interface QueryRequest {
  connection_id: number;
  query: string;
}

// API Methods
export const connectionApi = {
  // Create a new connection
  create: async (connection: Connection): Promise<Connection> => {
    const response = await api.post('/connections', connection);
    return response.data;
  },

  // List all connections
  list: async (): Promise<Connection[]> => {
    const response = await api.get('/connections/');
    return response.data;
  },

  // Delete a connection
  delete: async (id: number): Promise<void> => {
    await api.delete(`/connections/${id}/`);
  },

  // Update connection status
  updateStatus: async (id: number, status: string): Promise<void> => {
    await api.put(`/connections/${id}/status`, { status });
  },

  // Get schemas for a connection
  getSchemas: async (id: number): Promise<string[]> => {
    const response = await api.get(`/connections/${id}/schemas`);
    return response.data;
  },

  // Get tables for a connection with optional schema filter
  getTables: async (id: number, schema?: string): Promise<Table[]> => {
    const params = schema ? { schema } : {};
    const response = await api.get(`/connections/${id}/tables`, { params });
    return response.data;
  },
};

export const tableApi = {
  // Create table configuration
  create: async (config: TableConfig): Promise<TableConfig> => {
    const response = await api.post('/tables', config);
    return response.data;
  },

  // Delete table configuration
  delete: async (id: number): Promise<void> => {
    await api.delete(`/tables/${id}`);
  },

  // List table configurations
  list: async (): Promise<TableConfig[]> => {
    const response = await api.get('/tables');
    return response.data;
  },
};

export interface PillowFightStartResponse {
  connection_id: number;
  table_ids: number[];
  operation_types: string[];
  operation_delay: number;
  batch_size: number;
  status: string;
  fight_id: string;
}

export const pillowFightApi = {
  // Start pillow fight
  start: async (request: PillowFightRequest): Promise<PillowFightStartResponse> => {
    const response = await api.post('/v1/pillow-fight/start', request);
    return response.data;
  },

  // Get status
  getStatus: async (): Promise<PillowFightStatusResponse> => {
    const response = await api.get('/v1/pillow-fight/status');
    return response.data;
  },

  // Stop pillow fight
  stop: async (connectionId: number, tableId: number): Promise<void> => {
    await api.post(`/v1/pillow-fight/stop/${connectionId}/${tableId}`);
  },

  // Stop all pillow fights
  stopAll: async (): Promise<void> => {
    await api.post('/v1/pillow-fight/stop-all');
  },
};

export const automationApi = {
  // Execute SQL query
  executeQuery: async (request: QueryRequest): Promise<any> => {
    const response = await api.post(`/v1/automation/connections/${request.connection_id}/query`, request);
    return response.data;
  },
};

export default api;
