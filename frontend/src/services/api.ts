import axios from 'axios';

const resolveApiBaseUrl = (): string => {
  const envUrl = import.meta?.env?.VITE_API_BASE_URL?.trim();
  if (envUrl) {
    const normalized = envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
    return normalized.includes('/api') ? normalized : `${normalized}/api`;
  }

  if (typeof window !== 'undefined') {
    return `${window.location.origin}/api`;
  }

  // Fallback for non-browser contexts (e.g., tests)
  return 'http://localhost:8000/api';
};

const API_BASE_URL = resolveApiBaseUrl();

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
  db_type: 'mssql' | 'as400' | 'sqlite' | 'mysql' | 'postgresql' | 'oracle';
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
  operation_delay: number;
  batch_size: number;
  enabled: boolean;
  connection_id: number;
  operation_type?: 'all' | 'insert' | 'update' | 'delete';
}

export interface PillowFightJobRequest {
  connection_id: number;
  table_ids: number[];
  operation_type?: 'all' | 'insert' | 'update' | 'delete';
  operation_types?: Array<'all' | 'insert' | 'update' | 'delete'>;
  operation_delay?: number;
  batch_size?: number;
}

export interface PillowFightJobTableStatus {
  job_id: string;
  table_id: number;
  table_name?: string | null;
  schema_name?: string | null;
  status: string;
  insert_count: number;
  update_count: number;
  delete_count: number;
  error_count: number;
  last_operation_at?: string | null;
  resume_cursor?: string | null;
}

export interface PillowFightJobStatus {
  job_id: string;
  connection_id: number;
  status: string;
  operation_types: string[];
  operation_delay: number;
  batch_size: number;
  created_at: string;
  started_at?: string | null;
  completed_at?: string | null;
  last_heartbeat?: string | null;
  error_message?: string | null;
  tables: PillowFightJobTableStatus[];
}

export interface PillowFightJobStatusResponse {
  jobs: PillowFightJobStatus[];
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

  // Update a connection
  update: async (id: number, connection: Connection): Promise<Connection> => {
    const response = await api.put(`/connections/${id}`, connection);
    return response.data;
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

  // Update table configuration
  update: async (id: number, config: TableConfig): Promise<TableConfig> => {
    const response = await api.put(`/tables/${id}`, config);
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

export const pillowFightApi = {
  startJob: async (request: PillowFightJobRequest): Promise<PillowFightJobStatus> => {
    const response = await api.post('/v1/pillow-fight/jobs', request);
    return response.data;
  },

  listJobs: async (search?: string): Promise<PillowFightJobStatusResponse> => {
    const params = search ? { search } : undefined;
    const response = await api.get('/v1/pillow-fight/jobs', { params });
    return response.data;
  },

  getJob: async (jobId: string): Promise<PillowFightJobStatus> => {
    const response = await api.get(`/v1/pillow-fight/jobs/${jobId}`);
    return response.data;
  },

  stopJob: async (jobId: string): Promise<PillowFightJobStatus> => {
    const response = await api.post(`/v1/pillow-fight/jobs/${jobId}/stop`);
    return response.data;
  },

  stopTable: async (jobId: string, tableId: number): Promise<PillowFightJobStatus> => {
    const response = await api.post(`/v1/pillow-fight/jobs/${jobId}/tables/${tableId}/stop`);
    return response.data;
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
