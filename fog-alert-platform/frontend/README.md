# Fog Alert Platform - Frontend

A modern React TypeScript application for real-time road monitoring with fog detection, alerts, and interactive mapping.

## 📋 Table of Contents

- [Overview](#overview)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Application](#running-the-application)
- [Available Pages](#available-pages)
- [Building for Production](#building-for-production)
- [Connecting to Backend API](#connecting-to-backend-api)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This is the frontend for the Fog Alert Platform (AEGIS-RS), an intelligent road monitoring system. It provides:

- **6 Interactive Pages** - Overview, Dashboard, Live Monitoring, Alerts, Analytics, and Live Map
- **Real-time fog detection** - Display model predictions with probability scores
- **Beautiful UI** - Glass-morphism design with animated backgrounds (LineWaves WebGL)
- **Responsive Layout** - Works on desktop, tablet, and mobile devices
- **Dark Theme** - Eye-friendly interface optimized for 24/7 monitoring

## 🛠 Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| React | 19.2.4 | UI framework |
| TypeScript | 5.9 | Type-safe JavaScript |
| Vite | 8.0 | Build tool & dev server |
| Tailwind CSS | 4.x | Utility-first CSS framework |
| React Router | 6.x | Client-side routing |
| shadcn/ui | Latest | Pre-built UI components |
| LineWaves | - | WebGL animated background |
| OGL | - | WebGL rendering library |

## ✅ Prerequisites

Before you begin, ensure you have:

- **Node.js 18+** installed ([download](https://nodejs.org/))
- **npm** or **yarn** (comes with Node.js)
- **Visual Studio Code** or any text editor
- **Windows PowerShell** or terminal of your choice
- **Backend API running** on `http://localhost:8000` (see Backend README)

## 📁 Project Structure

```
frontend/
├── src/
│   ├── pages/               # Page components
│   │   ├── HomePage.tsx     # Overview with hero & LineWaves animation
│   │   ├── DashboardPage.tsx    # KPI cards & risk analysis
│   │   ├── LiveMonitoringPage.tsx   # Video stream & detection
│   │   ├── AlertsPage.tsx       # Real-time alert feed
│   │   ├── AnalyticsStatusPage.tsx  # System health & trends
│   │   └── LiveMapPage.tsx       # Interactive map with layers
│   ├── components/          # Reusable components
│   ├── App.tsx              # Main app shell with routing
│   ├── App.css              # Global animations & styling
│   ├── index.css            # Tailwind & theme tokens
│   └── main.tsx             # React entry point
├── public/                  # Static assets (favicon, fonts)
├── dist/                    # Built files (after npm run build)
├── vite.config.ts           # Vite configuration
├── tsconfig.json            # TypeScript configuration
├── components.json          # shadcn configuration
├── package.json             # Dependencies
├── tailwind.config.js       # Tailwind CSS config
└── README.md                # This file
```

## 🚀 Setup Instructions

### Step 1: Navigate to Frontend Directory

```powershell
cd fog-alert-platform/frontend
```

### Step 2: Install Dependencies

```powershell
npm install
```

This installs React, Vite, Tailwind CSS, shadcn/ui, and all other dependencies.

**Expected output:**
```
added XXX packages in X.XXs
```

### Step 3: Verify Installation

```powershell
npm list react
```

Should show React 19.2.4 or higher.

## ▶️ Running the Application

### Development Mode

```powershell
npm run dev
```

The app will start at `http://localhost:5173/` with Hot Module Reloading (HMR).

You should see:
```
  VITE v8.x.x  ready in XXX ms

  ➜  Local:   http://localhost:5173/
  ➜  press h + enter to show help
```

### Navigating the App

Once running, click the navigation links at the top:

1. **Home** - Overview with system status
2. **Dashboard** - Real-time KPIs and risk metrics
3. **Monitoring** - Live video feed and detection panel
4. **Alerts** - Alert history and severity filtering
5. **Analytics** - System performance and trends
6. **Map** - Interactive road map with hazard layers

## 📄 Available Pages

### 1. HomePage

**URL:** `/`

**Features:**
- Hero section with system introduction
- LineWaves WebGL animated background
- Quick access to main features
- Team and tech stack information

**Key Components:**
- Animated background (draws wave patterns)
- Call-to-action buttons
- Responsive grid layout

### 2. DashboardPage

**URL:** `/dashboard`

**Features:**
- KPI cards showing current metrics:
  - Risk Score (0-100)
  - Current Fog Level (%)
  - Visibility Distance (meters)
  - Active Alerts (count)
- Risk trend chart over time
- Fog level trend chart
- System status indicators

### 3. LiveMonitoringPage

**URL:** `/monitoring`

**Features:**
- Live video stream area (placeholder for camera feed)
- Real-time detection panel showing:
  - Detected objects (potholes, vehicles, etc.)
  - Confidence scores
  - Current fog level
- Before/after dehazing comparison

### 4. AlertsPage

**URL:** `/alerts`

**Features:**
- Real-time alert feed with severity levels
- Filter by severity (HIGH, MEDIUM, LOW)
- Alert details:
  - Location
  - Visibility
  - Recommended speed
  - Distance to hazard

### 5. AnalyticsStatusPage

**URL:** `/analytics`

**Features:**
- System performance analytics
- Performance metrics:
  - YOLOv8 model status
  - XGBoost model status
  - Average FPS
  - Average latency
  - API health status
  - Data stream status
- Historical analytics chart

### 6. LiveMapPage

**URL:** `/live-map`

**Features:**
- Full-screen interactive map
- Layer toggles:
  - Fog concentration areas
  - Pothole locations
  - Traffic signs
  - Speed bumps/humps
- Real-time marker updates
- Click markers for details

## 🏗️ Building for Production

### Create Optimized Build

```powershell
npm run build
```

This creates a `dist/` folder with optimized files.

**Expected output:**
```
✓ X modules transformed
✓ built in XXXms

dist/index.html                    X.XX kB | gzip: X.XX kB
dist/assets/index-*.js            XXX.XX kB | gzip: XXX.XX kB
dist/assets/index-*.css            XX.XX kB | gzip: X.XX kB
```

### Preview Production Build

```powershell
npm run preview
```

Server runs at `http://localhost:4173/` to preview the optimized build.

## 🔗 Connecting to Backend API

The frontend communicates with the backend at `http://localhost:8000`.

### Key Endpoints

**Health Check:**
```typescript
fetch('http://localhost:8000/api/health/')
  .then(r => r.json())
  .then(data => console.log(data))
```

**Fog Prediction:**
```typescript
const formData = new FormData()
formData.append('image', imageFile)

fetch('http://localhost:8000/api/fog/predict/', {
  method: 'POST',
  body: formData
})
  .then(r => r.json())
  .then(data => console.log(data)) // { fog_probability, prediction }
```

### Common Issues

**CORS Error:**
If you see "Access to XMLHttpRequest blocked", ensure:
1. Backend is running on port 8000
2. Backend has `CORS_ALLOWED_ORIGINS` including `http://localhost:5173`

**Connection Refused:**
If backend won't respond:
```powershell
# Check if backend is running
curl http://localhost:8000/api/health/

# If not, start it
cd ../backend
python manage.py runserver
```

## 🏗️ Component Structure

The main layout follows this hierarchy:

```
App.tsx (Router)
├── Navigation (NavLink)
├── Main Routes
│   ├── HomePage
│   ├── DashboardPage
│   ├── LiveMonitoringPage
│   ├── AlertsPage
│   ├── AnalyticsStatusPage
│   └── LiveMapPage
└── App.css (Global Styles)
```

### Adding a New Page

1. Create `src/pages/MyNewPage.tsx`:
```typescript
export default function MyNewPage() {
  return (
    <div className="page-container">
      <h1>My New Page</h1>
    </div>
  )
}
```

2. Add route in `App.tsx`:
```typescript
import MyNewPage from './pages/MyNewPage'

<Route path="/my-new-page" element={<MyNewPage />} />
```

3. Add nav link:
```html
<NavLink to="/my-new-page" className={({ isActive }) => ...}>
  My New Page
</NavLink>
```

## 🎨 Customizing Styles

### Theme Colors

Edit `src/index.css` for dark theme tokens:

```css
:root {
  --bg: #0f1320;           /* Main background */
  --text-h: #ffffff;       /* Heading text */
  --text-body: #a0aec0;    /* Body text */
  --primary: #4b84ff;      /* Primary color (blue) */
  --accent: #9b59ff;       /* Accent color (purple) */
}
```

### Animations

Edit `src/App.css` for animation timing and effects.

## 🐛 Troubleshooting

### Issue: "npm: command not found"

**Solution:** Install Node.js from https://nodejs.org/

### Issue: Port 5173 already in use

**Solution:** Kill the existing process or use a different port:
```powershell
npm run dev -- --port 5174
```

### Issue: Module not found errors

**Solution:** Reinstall dependencies:
```powershell
rm -r node_modules
npm install
```

### Issue: TypeScript compilation errors

**Solution:** Verify `tsconfig.json` path aliases are correct:
```json
"paths": {
  "@/*": ["./src/*"]
}
```

### Issue: Styles not applying

**Solution:** Check that Tailwind CSS is set up:
```powershell
npm run dev
# Look for "Using .../tailwind.config.js" in output
```

### Issue: Build too large

**Solution:** Check bundle size:
```powershell
npm run build
```

If gzipped size is > 500KB, consider code-splitting pages.

## 📊 Performance Tips

1. **Use React DevTools** - Check component renders
2. **Lazy load routes** - Split code by page
3. **Minimize re-renders** - Use React.memo for heavy components
4. **Optimize images** - Compress before upload
5. **Monitor bundle size** - Run `npm run build` to see file sizes

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [shadcn/ui Docs](https://ui.shadcn.com/)
- [React Router](https://reactrouter.com/)
- [Backend README](../backend/README.md)

## 🤝 Contributing

To add new features:

1. Create a feature branch: `git checkout -b feature/my-feature`
2. Add your component/page
3. Test locally: `npm run dev`
4. Build to verify: `npm run build`
5. Commit and push

## 📝 License

This project is part of the AEGIS-RS Road Monitoring System.

---

**Questions?** Check the [Backend README](../backend/README.md) for API details or open an issue on GitHub.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Oxc](https://oxc.rs)
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/)

## React Compiler

The React Compiler is not enabled on this template because of its impact on dev & build performances. To add it, see [this documentation](https://react.dev/learn/react-compiler/installation).

## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
