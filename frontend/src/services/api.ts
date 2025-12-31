import axios from 'axios';

const normalizePath = (path?: string | null): string => {
  if (!path) {
    return '';
  }
  const trimmed = path.trim();
  if (!trimmed) {
    return '';
  }
  const withLeading = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  return withLeading.endsWith('/') && withLeading !== '/' ? withLeading.slice(0, -1) : withLeading;
};

const detectContextBasePath = (): string => {
  const envBasePath = import.meta?.env?.VITE_APP_BASE_PATH?.trim();
  if (envBasePath) {
    return normalizePath(envBasePath);
  }

  if (typeof window === 'undefined') {
    return '';
  }

  const path = window.location.pathname || '';
  const segments = path.split('/').filter(Boolean);
  if (!segments.length) {
    return '';
  }

  const firstSegment = segments[0];
  const knownPrefixes = ['whisperer'];
  if (knownPrefixes.includes(firstSegment)) {
    return `/${firstSegment}`;
  }

  return '';
};

const resolveApiBaseUrl = (): string => {
  const envUrl = import.meta?.env?.VITE_API_BASE_URL?.trim();
  if (envUrl) {
    const normalized = envUrl.endsWith('/') ? envUrl.slice(0, -1) : envUrl;
    return normalized.includes('/api') ? normalized : `${normalized}/api`;
  }

  const basePath = detectContextBasePath();

  if (typeof window !== 'undefined') {
    const origin = window.location.origin;
    return basePath ? `${origin}${basePath}/api` : `${origin}/api`;
  }

  // Fallback for non-browser contexts (e.g., tests)
  return 'http://localhost:8000/api';
};

export const metadataApi = {
  // List objects (tables/views/procs) for a connection and optional schema
  listObjects: async (
    connectionId: number,
    schema?: string
  ): Promise<MetadataObject[]> => {
    const params = schema ? { schema } : {};
    const response = await api.get(
      `/connections/${connectionId}/metadata/objects`,
      { params }
    );
    return response.data;
  },

  // Get table metadata (columns, pk/fk, indexes)
  getTableMetadata: async (
    connectionId: number,
    tableName: string,
    schema?: string
  ): Promise<TableMetadata> => {
    const params = schema ? { schema } : {};
    const response = await api.get(
      `/connections/${connectionId}/metadata/tables/${tableName}`,
      { params }
    );
    return response.data;
  },
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
type SupportedDbType =
  | 'mssql'
  | 'as400'
  | 'sqlite'
  | 'mysql'
  | 'mariadb'
  | 'postgresql'
  | 'oracle';

export interface Connection {
  id?: number;
  name: string;
  description: string;
  db_type: SupportedDbType;
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

export interface MetadataObject {
  name: string;
  schema: string;
  type: string; // table, view, materialized_view, procedure, function, other
  has_children?: boolean;
}

export interface TableMetadata {
  table_name: string;
  schema_name: string;
  columns: Record<string, any>;
  primary_keys: string[];
  foreign_keys?: Array<Record<string, any>>;
  indexes?: Array<Record<string, any>>;
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

export interface ConnectionTestResponse {
  success: boolean;
  message: string;
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

  // Test a connection
  test: async (id: number): Promise<ConnectionTestResponse> => {
    const response = await api.post(`/connections/${id}/test`);
    return response.data;
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

  // Export query results to CSV
  exportQueryCsv: async (request: {
    connection_id: number;
    query: string;
    schema_name?: string;
    params?: any[];
    include_all_rows?: boolean;
    max_rows?: number;
  }): Promise<Blob> => {
    const response = await api.post(`/v1/automation/connections/${request.connection_id}/query/export-csv`, {
      query: request.query,
      schema_name: request.schema_name,
      params: request.params,
      include_all_rows: request.include_all_rows,
      max_rows: request.max_rows,
    }, {
      responseType: 'blob'
    });
    return response.data;
  },

  // Export table to CSV
  exportTableCsv: async (request: {
    connection_id: number;
    table_name: string;
    schema_name?: string;
  }): Promise<Blob> => {
    const response = await api.get(`/v1/automation/connections/${request.connection_id}/tables/${request.table_name}/export-csv`, {
      params: request.schema_name ? { schema_name: request.schema_name } : {},
      responseType: 'blob'
    });
    return response.data;
  },

  // Import CSV into table
  importTableCsv: async (request: {
    connection_id: number;
    table_name: string;
    schema_name?: string;
    file: File;
  }): Promise<{ success: boolean; inserted_rows: number }> => {
    const formData = new FormData();
    formData.append('file', request.file);
    
    const response = await api.post(`/v1/automation/connections/${request.connection_id}/tables/${request.table_name}/import-csv`, formData, {
      params: request.schema_name ? { schema_name: request.schema_name } : {},
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

export default api;
