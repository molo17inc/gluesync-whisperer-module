# Whisperer Frontend

A modern React frontend for the Whisperer database automation platform.

## Features

- **Connection Management**: Create and manage database connections (MS SQL, AS400, SQLite)
- **Table Configuration**: Configure tables for automated operations
- **Pillow Fight Control**: Start and monitor automated database operations
- **SQL Query Executor**: Execute custom SQL queries against your databases
- **Dashboard**: Overview of system status and configurations

## Technology Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for professional UI components
- **React Router** for navigation
- **Axios** for API communication
- **Vite** for fast development and building

## Getting Started

### Prerequisites

- Node.js 18+
- npm or yarn

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run dev
   ```

4. Open your browser and navigate to `http://localhost:5173`

### Build for Production

```bash
npm run build
```

## API Configuration

The frontend communicates with the Whisperer backend API. By default, it expects the API to be running on `http://localhost:1717`. You can change this by setting the `REACT_APP_API_URL` environment variable.

## Usage

### Creating a Database Connection

1. Go to the "Connections" tab
2. Click "New Connection"
3. Fill in the connection details (host, port, credentials, database type)
4. Click "Create"

### Configuring Tables

1. Go to the "Tables" tab
2. Click "Configure Table"
3. Select a connection and browse schemas/tables
4. Set operation type and timing parameters
5. Click "Configure Table"

### Running Pillow Fight

1. Go to the "Pillow Fight" tab
2. Click "Start Pillow Fight"
3. Select connection and tables
4. Configure operation settings
5. Click "Start Pillow Fight"

### Executing Queries

1. Go to the "Query" tab
2. Select a database connection
3. Enter your SQL query
4. Click "Execute Query"

## Development

### Project Structure

```
src/
├── components/          # React components
│   ├── Dashboard.tsx    # Main dashboard
│   ├── Connections.tsx  # Connection management
│   ├── Tables.tsx       # Table configuration
│   ├── PillowFight.tsx  # Automation control
│   ├── Query.tsx        # SQL query execution
│   └── Navigation.tsx   # App navigation
├── services/            # API services
│   └── api.ts          # API client and types
├── App.tsx             # Main app component
└── main.tsx           # App entry point
```

### Available Scripts

- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run preview` - Preview production build

## Backend Integration

This frontend is designed to work with the Whisperer backend API. Make sure the backend is running and accessible before using the frontend.
