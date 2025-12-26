import React from "react";
import { Routes, Route, Link, useLocation } from "react-router-dom";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import {
  Container,
  Box,
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Drawer,
  List,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Divider,
} from "@mui/material";
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Storage as StorageIcon,
  TableChart as TableChartIcon,
  PlayArrow as PlayArrowIcon,
  Code as CodeIcon,
} from "@mui/icons-material";
import Dashboard from "./components/Dashboard";
import Connections from "./components/Connections";
import Tables from "./components/Tables";
import PillowFight from "./components/PillowFight";
import Query from "./components/Query";

// Gluesync Logo Component
const GluesyncLogo = () => (
  <svg
    width="32"
    height="32"
    viewBox="0 0 100 100"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
  >
    <path
      d="M93.22 0H6.78C3.027 0 0 3.027 0 6.78V93.22C0 96.975 3.027 100 6.78 100H93.22C96.975 100 100 96.975 100 93.22V6.78C100 3.027 96.975 0 93.22 0Z"
      fill="#E30A17"
    />
    <path
      d="M49.298 18C36.151 18 22 21.107 22 27.927V72.596C22 78.559 32.825 81.686 44.335 82.374V77.408C33.083 76.713 27.294 73.775 26.964 72.596V63.732C31.2 65.856 37.649 67.067 44.335 67.469V62.518C33.083 61.823 27.294 58.883 26.964 57.706V48.842C32.245 51.49 40.967 52.743 49.298 52.743C62.446 52.743 76.596 49.636 76.596 42.817V27.924C76.594 21.105 62.446 18 49.298 18ZM26.961 27.964C27.338 26.587 34.781 22.964 49.298 22.964C63.687 22.964 71.124 26.522 71.625 27.927C71.124 29.331 63.687 32.89 49.298 32.89C34.781 32.89 27.338 29.267 26.961 27.964ZM71.633 42.784C71.233 44.167 63.793 47.78 49.298 47.78C34.781 47.78 27.338 44.157 26.964 42.817V33.952C32.245 36.6 40.967 37.853 49.298 37.853C57.629 37.853 66.352 36.6 71.633 33.952V42.784Z"
      fill="white"
    />
    <path
      d="M76.1921 51.9534L76.1921 56.9164C62.4931 56.9314 51.3901 68.0344 51.3751 81.7324L46.4121 81.7324C46.4301 65.2944 59.7531 51.9704 76.1921 51.9534Z"
      fill="white"
    />
    <path
      d="M76.7036 62.3911L76.7036 67.3541C68.4846 67.3641 61.8246 74.0251 61.8146 82.2441L56.8516 82.2441C56.8636 71.2851 65.7456 62.4031 76.7036 62.3911Z"
      fill="white"
    />
    <path
      d="M76.5579 72.1736L76.5579 77.1366C73.8189 77.1386 71.5969 79.3596 71.5949 82.0996L66.6319 82.0996C66.6369 76.6206 71.0789 72.1786 76.5579 72.1736Z"
      fill="white"
    />
  </svg>
);
// Theme configuration
const theme = createTheme({
  palette: {
    primary: {
      main: "#000000",
    },
    secondary: {
      main: "#393939",
    },
  },
  typography: {
    fontFamily:
      '"IBM Plex Sans", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  },
});

// Drawer width
const drawerWidth = 240;

const App: React.FC = () => {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const location = useLocation();

  console.log("App component rendered");
  console.log("Current location:", location.pathname);

  const isActive = (path: string) => location.pathname === path;

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const drawer = (
    <div>
      <Toolbar>
        <GluesyncLogo />
        <Typography variant="h6" noWrap component="div" sx={{ ml: 2 }}>
          Whisperer
        </Typography>
      </Toolbar>
      <Divider />
      <List>
        <ListItem disablePadding>
          <ListItemButton component={Link} to="/" selected={isActive("/")}>
            <ListItemIcon>
              <DashboardIcon />
            </ListItemIcon>
            <ListItemText primary="Dashboard" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            component={Link}
            to="/connections"
            selected={isActive("/connections")}
          >
            <ListItemIcon>
              <StorageIcon />
            </ListItemIcon>
            <ListItemText primary="Connections" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            component={Link}
            to="/tables"
            selected={isActive("/tables")}
          >
            <ListItemIcon>
              <TableChartIcon />
            </ListItemIcon>
            <ListItemText primary="Tables" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            component={Link}
            to="/pillowfight"
            selected={isActive("/pillowfight")}
          >
            <ListItemIcon>
              <PlayArrowIcon />
            </ListItemIcon>
            <ListItemText primary="Pillow fight" />
          </ListItemButton>
        </ListItem>
        <ListItem disablePadding>
          <ListItemButton
            component={Link}
            to="/query"
            selected={isActive("/query")}
          >
            <ListItemIcon>
              <CodeIcon />
            </ListItemIcon>
            <ListItemText primary="Query" />
          </ListItemButton>
        </ListItem>
      </List>
    </div>
  );

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Box sx={{ display: "flex" }}>
        <AppBar
          position="fixed"
          sx={{
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            ml: { sm: `${drawerWidth}px` },
          }}
        >
          <Toolbar>
            <IconButton
              color="inherit"
              aria-label="open drawer"
              edge="start"
              onClick={handleDrawerToggle}
              sx={{ mr: 2, display: { sm: "none" } }}
            >
              <MenuIcon />
            </IconButton>
            <Typography variant="h6" noWrap component="div">
              Database automation tool
            </Typography>
          </Toolbar>
        </AppBar>

        <Box
          component="nav"
          sx={{ width: { sm: drawerWidth }, flexShrink: { sm: 0 } }}
        >
          <Drawer
            variant="temporary"
            open={mobileOpen}
            onClose={handleDrawerToggle}
            ModalProps={{
              keepMounted: true,
            }}
            sx={{
              display: { xs: "block", sm: "none" },
              "& .MuiDrawer-paper": {
                boxSizing: "border-box",
                width: drawerWidth,
              },
            }}
          >
            {drawer}
          </Drawer>
          <Drawer
            variant="permanent"
            sx={{
              display: { xs: "none", sm: "block" },
              "& .MuiDrawer-paper": {
                boxSizing: "border-box",
                width: drawerWidth,
              },
            }}
            open
          >
            {drawer}
          </Drawer>
        </Box>

        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            width: { sm: `calc(100% - ${drawerWidth}px)` },
            mt: "64px",
          }}
        >
          <Container maxWidth="xl">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/connections" element={<Connections />} />
              <Route path="/tables" element={<Tables />} />
              <Route path="/pillowfight" element={<PillowFight />} />
              <Route path="/query" element={<Query />} />
            </Routes>
          </Container>
        </Box>
      </Box>
    </ThemeProvider>
  );
};

export default App;
