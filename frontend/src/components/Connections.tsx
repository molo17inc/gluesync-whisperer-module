import React, { useState, useEffect } from "react";
import {
  Box,
  Typography,
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  IconButton,
  Alert,
  Snackbar,
} from "@mui/material";
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  Edit as EditIcon,
  PlayArrow as PlayArrowIcon,
} from "@mui/icons-material";
import { Connection, connectionApi } from "../services/api";

const Connections: React.FC = () => {
  const [connections, setConnections] = useState<Connection[]>([]);
  const [editingConnection, setEditingConnection] = useState<Connection | null>(
    null
  );
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [snackbar, setSnackbar] = useState<{
    open: boolean;
    message: string;
    severity: "success" | "error";
  }>({
    open: false,
    message: "",
    severity: "success",
  });

  const [formData, setFormData] = useState({
    name: "",
    description: "",
    db_type: "sqlite" as
      | "mssql"
      | "as400"
      | "sqlite"
      | "postgresql"
      | "mysql"
      | "oracle",
    host: "localhost",
    port: 3306, // Default MySQL port
    username: "",
    password: "",
    database: "",
  });

  useEffect(() => {
    loadConnections();
  }, []);

  const loadConnections = async () => {
    try {
      setLoading(true);
      const data = await connectionApi.list();
      setConnections([...data]);
    } catch (error) {
      showSnackbar("Failed to load connections", "error");
    } finally {
      setLoading(false);
    }
  };

  const showSnackbar = (message: string, severity: "success" | "error") => {
    setSnackbar({ open: true, message, severity });
  };

  const handleCloseDialog = () => {
    setOpen(false);
    setEditingConnection(null);
    setFormData({
      name: "",
      description: "",
      db_type: "sqlite",
      host: "localhost",
      port: 3306,
      username: "",
      password: "",
      database: "",
    });
  };

  const handleInputChange = (field: keyof typeof formData, value: any) => {
    setFormData((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async () => {
    try {
      if (editingConnection) {
        // Update existing connection
        await connectionApi.update(
          editingConnection.id!,
          formData as Connection
        );
        showSnackbar("Connection updated successfully", "success");
      } else {
        // Create new connection
        await connectionApi.create(formData as Connection);
        showSnackbar("Connection created successfully", "success");
      }
      handleCloseDialog();
      loadConnections();
    } catch (error) {
      const errorMessage =
        (error as any)?.response?.data?.detail ||
        `Failed to ${editingConnection ? "update" : "create"} connection`;
      showSnackbar(errorMessage, "error");
    }
  };

  const handleDelete = async (id: number) => {
    if (window.confirm("Are you sure you want to delete this connection?")) {
      try {
        await connectionApi.delete(id);
        showSnackbar("Connection deleted successfully", "success");
        loadConnections();
      } catch (error) {
        showSnackbar("Failed to delete connection", "error");
      }
    }
  };

  const handleEdit = (connection: Connection) => {
    setEditingConnection(connection);
    setFormData({
      name: connection.name,
      description: connection.description || "",
      db_type: connection.db_type,
      host: connection.host,
      port: connection.port,
      username: connection.username,
      password: connection.password,
      database: connection.database || connection.database_name || "",
    });
    setOpen(true);
  };

  const handleTestConnection = async (id: number) => {
    try {
      showSnackbar("Testing connection...", "success");
      const response = await connectionApi.test(id);
      showSnackbar(response.message, response.success ? "success" : "error");
      loadConnections();
    } catch (error: any) {
      const message =
        error?.response?.data?.message ||
        error?.response?.data?.detail ||
        "Unable to test connection";
      showSnackbar(message, "error");
    }
  };

  const getStatusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case "connected":
        return "success";
      case "error":
        return "error";
      case "idle":
        return "default";
      case "running":
        return "primary";
      default:
        return "default";
    }
  };

  return (
    <Box>
      <Box
        sx={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          mb: 3,
        }}
      >
        <Typography variant="h4">Database connections</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => {
            setFormData({
              name: "",
              description: "",
              db_type: "sqlite",
              host: "localhost",
              port: 5432,
              username: "",
              password: "",
              database: "",
            });
            setOpen(true);
          }}
        >
          Create Connection
        </Button>
      </Box>

      <Card>
        <CardContent>
          <TableContainer>
            <Table sx={{ minWidth: 650 }} aria-label="connections table">
              <TableHead>
                <TableRow>
                  <TableCell>Name</TableCell>
                  <TableCell>Type</TableCell>
                  <TableCell>Host</TableCell>
                  <TableCell>Database</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {(Array.isArray(connections) ? connections : []).map(
                  (connection) => (
                    <TableRow key={connection.id}>
                      <TableCell>
                        <Box>
                          <Typography variant="body1" fontWeight="medium">
                            {connection.name}
                          </Typography>
                          {connection.description && (
                            <Typography variant="body2" color="text.secondary">
                              {connection.description}
                            </Typography>
                          )}
                        </Box>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={(
                            connection.db_type || "UNKNOWN"
                          ).toUpperCase()}
                          size="small"
                          color="primary"
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        {connection.host}:{connection.port}
                      </TableCell>
                      <TableCell>
                        {connection.database || connection.database_name || "-"}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={(connection.status || "unknown").toUpperCase()}
                          size="small"
                          color={getStatusColor(connection.status)}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Button
                          variant="outlined"
                          size="small"
                          startIcon={<PlayArrowIcon />}
                          onClick={() => handleTestConnection(connection.id!)}
                          sx={{ mr: 1 }}
                        >
                          Test
                        </Button>
                        <IconButton
                          onClick={() => handleEdit(connection)}
                          color="secondary"
                          size="small"
                        >
                          <EditIcon />
                        </IconButton>
                        <IconButton
                          onClick={() => handleDelete(connection.id!)}
                          color="error"
                          size="small"
                        >
                          <DeleteIcon />
                        </IconButton>
                      </TableCell>
                    </TableRow>
                  )
                )}
                {connections.length === 0 && !loading && (
                  <TableRow>
                    <TableCell colSpan={6} align="center" sx={{ py: 4 }}>
                      <Typography variant="body2" color="text.secondary">
                        No connections found. Create your first connection to
                        get started.
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      {/* Create/Edit Connection Dialog */}
      <Dialog open={open} onClose={handleCloseDialog} maxWidth="md" fullWidth>
        <DialogTitle>
          {editingConnection ? "Edit Connection" : "Create New Connection"}
        </DialogTitle>
        <DialogContent>
          <Box sx={{ pt: 2, display: "flex", flexDirection: "column", gap: 2 }}>
            <TextField
              label="Name"
              value={formData.name}
              onChange={(e) => handleInputChange("name", e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Description"
              value={formData.description}
              onChange={(e) => handleInputChange("description", e.target.value)}
              fullWidth
            />
            <FormControl fullWidth required>
              <InputLabel>Database Type</InputLabel>
              <Select
                value={formData.db_type}
                label="Database Type"
                onChange={(e) => {
                  const dbType = e.target.value as
                    | "mssql"
                    | "as400"
                    | "sqlite"
                    | "postgresql"
                    | "mysql"
                    | "oracle";
                  handleInputChange("db_type", dbType);
                  // Set default port based on database type
                  const defaultPorts = {
                    sqlite: 0, // SQLite doesn't use ports
                    mysql: 3306,
                    postgresql: 5432,
                    mssql: 1433,
                    oracle: 1521, // Oracle default port
                    as400: 446, // Common AS400 port
                  };
                  if (defaultPorts[dbType] !== formData.port) {
                    handleInputChange("port", defaultPorts[dbType]);
                  }
                }}
              >
                <MenuItem value="sqlite">SQLite</MenuItem>
                <MenuItem value="mysql">MySQL</MenuItem>
                <MenuItem value="postgresql">PostgreSQL</MenuItem>
                <MenuItem value="oracle">Oracle</MenuItem>
                <MenuItem value="mssql">MS SQL Server</MenuItem>
                <MenuItem value="as400">AS400</MenuItem>
              </Select>
            </FormControl>
            <TextField
              label="Host"
              value={formData.host}
              onChange={(e) => handleInputChange("host", e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Port"
              type="number"
              value={formData.port}
              onChange={(e) =>
                handleInputChange("port", parseInt(e.target.value) || 5432)
              }
              fullWidth
              required
            />
            <TextField
              label="Username"
              value={formData.username}
              onChange={(e) => handleInputChange("username", e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Password"
              type="password"
              value={formData.password}
              onChange={(e) => handleInputChange("password", e.target.value)}
              fullWidth
              required
            />
            <TextField
              label="Database"
              value={formData.database}
              onChange={(e) => handleInputChange("database", e.target.value)}
              fullWidth
              helperText="Database name (required for MySQL, PostgreSQL, Oracle, MS SQL) or leave empty for AS400"
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button
            onClick={handleSubmit}
            variant="contained"
            disabled={
              !formData.name ||
              !formData.host ||
              !formData.username ||
              !formData.password ||
              (formData.db_type !== "as400" &&
                formData.db_type !== "sqlite" &&
                !formData.database)
            }
          >
            {editingConnection ? "Update" : "Create"}
          </Button>
        </DialogActions>
      </Dialog>

      <Snackbar
        open={snackbar.open}
        autoHideDuration={6000}
        onClose={() => setSnackbar({ ...snackbar, open: false })}
      >
        <Alert
          onClose={() => setSnackbar({ ...snackbar, open: false })}
          severity={snackbar.severity}
          sx={{ width: "100%" }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Connections;
