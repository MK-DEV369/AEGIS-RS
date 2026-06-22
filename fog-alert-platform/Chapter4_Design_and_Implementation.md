# Chapter 4: Design and Implementation

This chapter presents the design and implementation of the proposed **AEGIS-RS** system as a full-stack AI, IoT, and cloud-based road hazard intelligence platform. The chapter is organized to describe the system architecture, the fog and pothole detection pipelines, the risk assessment engine, the telemetry layer, backend and frontend design, AWS deployment, database schema, API communication, real-time streaming, performance optimization, and system integration.

## 4.1 System Architecture

The overall architecture follows a layered design in which sensing, AI inference, backend processing, storage, visualization, and cloud deployment are separated into clear modules. This improves maintainability, deployment flexibility, and scaling.

### Figure 4.1: Overall System Architecture

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.9\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Overall Architecture Diagram Here]}\\[0.5cm]
    Phone / IP Camera $\rightarrow$ Frame Capture $\rightarrow$ Dehazing (FFA-Net) $\rightarrow$\\
    Fog Detection (XGBoost) $+$ Pothole Detection (YOLOv8) $\rightarrow$ Risk Engine $\rightarrow$\\
    Django REST Backend $\rightarrow$ Database / Telemetry $\rightarrow$ React Dashboard $\rightarrow$ AWS Cloud Deployment
    \vspace{1cm}
    }}
    \caption{High-level architecture of the AEGIS-RS platform.}
    \label{fig:overall-architecture}
\end{figure}
```

The architecture can be interpreted in four major layers:

- **Edge layer**: camera devices, phone sensors, and optional ESP32-based alert hardware.
- **AI layer**: fog dehazing, fog classification, pothole detection, and risk inference.
- **Communication layer**: REST APIs, streaming endpoints, telemetry ingestion, and JSON responses.
- **Cloud layer**: frontend hosting, backend deployment, data persistence, monitoring, and scaling on AWS.

## 4.2 Overall Workflow

The system workflow begins with frame acquisition from the camera stream. Each frame is preprocessed and then sent through the fog and pothole pipelines. The outputs are fused by the risk engine, stored in the database, and visualized on the dashboard.

### Figure 4.2: End-to-End Workflow

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.92\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Overall Workflow Diagram Here]}\\[0.4cm]
    Capture Frame $\rightarrow$ Preprocess $\rightarrow$ AI Inference $\rightarrow$ Risk Fusion $\rightarrow$ API Response $\rightarrow$\\
    Database Storage $\rightarrow$ Frontend Rendering $\rightarrow$ Alert Generation $\rightarrow$ Cloud Logging
    \vspace{1cm}
    }}
    \caption{Operational workflow of the integrated hazard detection system.}
    \label{fig:overall-workflow}
\end{figure}
```

## 4.3 Fog Detection Pipeline

The fog pipeline estimates haze severity and visibility using a combination of image enhancement and machine learning. The dehazing stage improves image quality before feature extraction.

### Figure 4.3: Fog Detection Pipeline

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.9\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Fog Pipeline Diagram Here]}\\[0.4cm]
    Camera Frame $\rightarrow$ Preprocessing $\rightarrow$ FFA-Net Dehazing $\rightarrow$\\
    Feature Extraction (Contrast, Brightness, Edge Density) $\rightarrow$\\
    XGBoost Classifier $\rightarrow$ EMA Smoothing $\rightarrow$ Fog Level + Visibility
    \vspace{1cm}
    }}
    \caption{Fog detection and visibility estimation pipeline.}
    \label{fig:fog-pipeline}
\end{figure}
```

### Mathematical Formulation

Atmospheric scattering is represented as:

$$
I(x) = J(x)t(x) + A\bigl(1 - t(x)\bigr)
$$

where $I(x)$ is the observed hazy image, $J(x)$ is the scene radiance, $t(x)$ is the transmission map, and $A$ is the global atmospheric light.

Visibility is inversely related to contrast:

$$
Visibility \propto \frac{1}{Contrast}
$$

Temporal smoothing is applied using exponential moving average (EMA):

$$
F_t = \alpha f_t + (1 - \alpha)F_{t-1}
$$

where $f_t$ is the current fog probability and $F_{t-1}$ is the previously smoothed value.

### Design Rationale

- **Dehazing is required** because fog reduces contrast, removes edges, and degrades downstream detection performance.
- **Temporal smoothing is required** because frame-by-frame predictions can fluctuate under changing light and motion blur.
- **XGBoost is used** because it performs well on structured image features such as contrast, edge density, and brightness, while remaining efficient for real-time inference.

## 4.4 Pothole Detection Pipeline

The pothole pipeline detects road surface defects in real time using a lightweight YOLOv8 model and converts the detection output into severity-aware risk metrics.

### Figure 4.4: Pothole Detection Pipeline

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.9\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Pothole Pipeline Diagram Here]}\\[0.4cm]
    Camera Stream $\rightarrow$ Frame Capture $\rightarrow$ YOLOv8 Detection $\rightarrow$\\
    Bounding Box Extraction $\rightarrow$ Size / Distance Estimation $\rightarrow$\\
    Severity Classification $\rightarrow$ GPS Tagging $\rightarrow$ ESP32 Alert Trigger
    \vspace{1cm}
    }}
    \caption{Pothole detection, localization, and severity estimation pipeline.}
    \label{fig:pothole-pipeline}
\end{figure}
```

### Mathematical Formulation

Intersection over Union (IoU) is defined as:

$$
IoU = \frac{Area(B \cap G)}{Area(B \cup G)}
$$

where $B$ is the predicted bounding box and $G$ is the ground-truth region.

The pothole risk score is expressed as:

$$
R = 0.4S + 0.3D + 0.3P
$$

where $S$ is pothole size, $D$ is depth, and $P$ is proximity.

### Design Rationale

- **YOLOv8n is chosen** because it offers strong trade-off between detection accuracy and inference speed.
- **Real-time inference** is needed because pothole warnings must be issued while the vehicle is still approaching the hazard.
- **Severity classification** improves interpretability by converting raw detections into actionable alert levels.

## 4.5 Risk Assessment Engine

The risk engine is the main decision layer of the system. It combines fog severity, pothole risk, visibility, and contextual data into a unified hazard score.

### Figure 4.5: Risk Fusion Model

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.75\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Risk Fusion Diagram Here]}\\[0.4cm]
    Fog Score $+$ Visibility $+$ Pothole Risk $+$ GPS Context $\rightarrow$ Unified Risk Engine $\rightarrow$ Alert Classification
    \vspace{1cm}
    }}
    \caption{Unified multi-hazard risk assessment mechanism.}
    \label{fig:risk-fusion}
\end{figure}
```

### Risk Equation

$$
Risk = w_1F + w_2V^{-1} + w_3P + w_4T
$$

where $F$ is fog score, $V$ is visibility, $P$ is pothole risk, and $T$ represents telemetry or contextual factors such as source metadata and GPS state.

### Design Rationale

- **Multi-hazard fusion** allows the platform to detect and score compound driving risks.
- **Decision intelligence** improves over single-model outputs by considering the interaction between hazards.
- **Dynamic risk adaptation** enables alert levels to change according to real-time conditions.

## 4.6 GPS and Telemetry Integration

Telemetry is used to attach spatial context to detections. GPS data from mobile devices or an embedded controller is transmitted to the backend together with the frame request or event payload.

### Figure 4.6: Telemetry Flow

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.75\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Telemetry Flow Diagram Here]}\\[0.4cm]
    ESP32 / Phone GPS $\rightarrow$ Telemetry API $\rightarrow$ Database Storage $\rightarrow$ Map Visualization $\rightarrow$ Risk Heatmap
    \vspace{1cm}
    }}
    \caption{Telemetry and GPS synchronization pipeline.}
    \label{fig:telemetry-flow}
\end{figure}
```

### Design Rationale

- **Source tracking** ensures that detections can be linked to a specific stream, device, or vehicle.
- **GPS accuracy** improves the usefulness of alerts by allowing spatial mapping of hazards.
- **Telemetry synchronization** ensures that detection records and positional metadata remain aligned in time.

## 4.7 Backend System Design

The backend is implemented using Django and Django REST Framework. It acts as the integration hub for AI inference, telemetry processing, persistence, and frontend communication.

### Figure 4.7: Backend Architecture

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.8\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Backend Architecture Diagram Here]}\\[0.4cm]
    Django REST API $\rightarrow$ Fog Service $\rightarrow$ Pothole Service $\rightarrow$\\
    Telemetry Service $\rightarrow$ Stream Service $\rightarrow$ Analytics Service $\rightarrow$ Cache Manager
    \vspace{1cm}
    }}
    \caption{Backend module decomposition and service relationships.}
    \label{fig:backend-architecture}
\end{figure}
```

### Main Backend Modules

- **fog_api/services.py**: core ML inference, dehazing, detection fusion, and risk scoring.
- **fog_api/views.py**: REST API request handling and response serialization.
- **fog_api/models.py**: database entities for fog and pothole detections, telemetry, and runtime state.
- **fog_api/runtime_state.py**: in-memory state tracking for smoothing, deduplication, and source status.
- **fog_api/urls.py**: endpoint routing and API organization.

### Request Flow

1. Client sends a JSON or binary frame request.
2. Django routes the request to the corresponding view.
3. The service layer decodes the frame and performs inference.
4. Results are enriched with metrics, GPS data, and timing information.
5. The response is returned as JSON and stored in the database.

## 4.8 Frontend Dashboard Design

The frontend is built with React and Vite. It provides real-time visualization of fog severity, pothole detections, alerts, analytics, and map-based hazard tracking.

### Figure 4.8: Frontend Architecture

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.75\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Frontend Architecture Diagram Here]}\\[0.4cm]
    React Frontend $\rightarrow$ Dashboard $\rightarrow$ Live Monitoring $\rightarrow$ Alerts $\rightarrow$ Analytics $\rightarrow$ Live Map
    \vspace{1cm}
    }}
    \caption{Frontend module layout and user interaction flow.}
    \label{fig:frontend-architecture}
\end{figure}
```

### Screenshots to Include

- Dashboard overview page.
- Live monitoring stream page.
- Alert summary panel.
- Live map with geotagged hazard markers.

### Design Rationale

- The dashboard prioritizes real-time visibility and simple risk interpretation.
- Map visualization is used to convert detections into spatial intelligence.
- The frontend consumes the backend JSON API directly for consistent state rendering.

## 4.9 AWS Cloud Architecture

The deployment strategy uses AWS to host the frontend, backend, persistent storage, and observability stack.

### Figure 4.9: AWS Deployment Architecture

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.72\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert AWS Deployment Diagram Here]}\\[0.4cm]
    CloudFront $\rightarrow$ React Frontend (S3) $\rightarrow$ ECS / EC2 Backend $\rightarrow$\\
    RDS PostgreSQL $\rightarrow$ CloudWatch Monitoring
    \vspace{1cm}
    }}
    \caption{Cloud deployment architecture on AWS.}
    \label{fig:aws-architecture}
\end{figure}
```

### Design Rationale

- **Scalability**: container-based deployment allows horizontal scaling of backend workloads.
- **Monitoring**: CloudWatch provides logs, metrics, and alerting for model inference and API health.
- **Storage**: RDS stores structured detection events and telemetry records.
- **Deployment**: CloudFront and S3 provide efficient delivery of the frontend application.

## 4.10 Database Design

The database stores detection history, telemetry records, runtime state, and metadata required for analytics and dashboard rendering.

### Figure 4.10: Entity Relationship Diagram

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.78\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert ER Diagram Here]}\\[0.4cm]
    FogDetection $\leftrightarrow$ Telemetry\\
    PotholeDetection $\leftrightarrow$ Telemetry\\
    RuntimeState $\leftrightarrow$ Source Tracking\\
    \vspace{1cm}
    }}
    \caption{Logical database relationships used by the backend.}
    \label{fig:er-diagram}
\end{figure}
```

### Core Tables

- **FogDetection**: fog probability, smoothed score, visibility, contrast, risk score, dehazing metadata.
- **PotholeDetection**: pothole metrics, counts, risk values, annotated frames, frame metadata.
- **Telemetry**: GPS coordinates, source identifiers, timestamps, and device context.
- **RuntimeState**: source health, deduplication state, and temporal smoothing cache.

### Database Design Notes

- Use indexed timestamp fields for fast retrieval of recent events.
- Store structured metrics in JSON fields when detection outputs vary by pipeline.
- Preserve source identifiers to support multi-device monitoring.

## 4.11 API Design and Communication

The backend exposes REST endpoints for prediction, stream monitoring, telemetry ingestion, and system management.

### Figure 4.11: API Communication Flow

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.68\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert API Flow Diagram Here]}\\[0.4cm]
    Camera $\rightarrow$ POST /predict $\rightarrow$ AI Processing $\rightarrow$ JSON Response $\rightarrow$ Frontend Rendering
    \vspace{1cm}
    }}
    \caption{API-based request and response communication model.}
    \label{fig:api-flow}
\end{figure}
```

### Example JSON Response

```json
{
  "fog_probability": 0.65,
  "fog_probability_smoothed": 0.62,
  "fog_level": "MEDIUM",
  "visibility_meters": 45.3,
  "contrast": 0.087,
  "risk_score": 0.48,
  "pothole_count": 3,
  "latency_ms": 182.4
}
```

### API Design Notes

- JSON is used for structured responses to ensure frontend compatibility.
- Binary image payloads are used for frame-based inference and annotated preview generation.
- Endpoints are organized by function to keep fog, pothole, telemetry, and system logic separated.

## 4.12 Real-Time Streaming Pipeline

Real-time stream handling is required for continuous hazard monitoring. The backend receives frames, processes them, annotates the results, and returns updated visual output to the frontend.

### Figure 4.12: Streaming Architecture

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.72\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Streaming Pipeline Diagram Here]}\\[0.4cm]
    Phone Camera $\rightarrow$ MJPEG Stream $\rightarrow$ Backend Relay $\rightarrow$ AI Annotation $\rightarrow$ Frontend Stream
    \vspace{1cm}
    }}
    \caption{Real-time streaming and annotation pipeline.}
    \label{fig:streaming-pipeline}
\end{figure}
```

### Design Considerations

- **Latency** must be kept low to preserve the usefulness of live alerts.
- **Frame handling** uses resizing and selective processing to balance quality and speed.
- **Streaming optimization** may use caching or chunked processing for repeated frames.

## 4.13 Performance Optimization

The system is designed for efficient inference and responsive API behavior.

### Optimization Strategies

- Lightweight YOLOv8n model selection for fast pothole detection.
- Frame resizing before inference to reduce computational load.
- EMA smoothing to suppress noisy fluctuations in fog probability.
- Caching of runtime state and recent results for repeated source requests.
- Batch-friendly processing and memory cleanup after inference.

### Performance Table

| Component | Latency |
|-----------|---------|
| Dehazing | 40 ms |
| Fog Prediction | 60 ms |
| YOLOv8 Detection | 120 ms |
| API Response | 20 ms |

### Design Rationale

The performance strategy focuses on maintaining interactive response times while preserving enough accuracy for operational hazard detection.

## 4.14 System Integration

This section describes how the modules communicate as a complete system.

### Figure 4.13: Integrated Pipeline

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.9\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Integrated Pipeline Diagram Here]}\\[0.4cm]
    Camera $\rightarrow$ AI Models $\rightarrow$ Risk Engine $\rightarrow$ Backend $\rightarrow$ Database $\rightarrow$ Dashboard $\rightarrow$ ESP32 Alerts $\rightarrow$ AWS
    \vspace{1cm}
    }}
    \caption{Complete integrated data and control flow.}
    \label{fig:integrated-pipeline}
\end{figure}
```

### Integration Explanation

The integrated system works as follows:

1. Frames arrive from the live camera stream or stored media source.
2. The dehazing module improves visibility where fog is detected.
3. The fog and pothole models independently infer hazard-related outputs.
4. The risk engine merges multiple signals into one decision layer.
5. The backend stores and exposes results through API endpoints.
6. The frontend displays detections, maps, alerts, and analytics.
7. Telemetry is synchronized so that each event can be spatially tracked.
8. AWS deployment supports availability, observability, and scaling.

## 4.15 Chapter Summary

The proposed architecture integrates computer vision, machine learning, telemetry, and cloud-native deployment into a unified real-time hazard intelligence framework. The system successfully combines fog detection, pothole detection, risk scoring, GPS tracking, backend orchestration, frontend visualization, and AWS deployment into a single engineering solution.

### Additional Recommended Insertions

#### Sequence Diagram Placeholder

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.8\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Sequence Diagram Here]}\\[0.4cm]
    Camera $\rightarrow$ Backend $\rightarrow$ AI $\rightarrow$ Database $\rightarrow$ Dashboard $\rightarrow$ ESP32
    \vspace{1cm}
    }}
    \caption{Sequence of interactions between the main system components.}
\end{figure}
```

#### Data Flow Diagram Placeholder

```latex
\begin{figure}[H]
    \centering
    \fbox{%
    \parbox{0.8\linewidth}{
    \centering
    \vspace{1cm}
    \textbf{[Insert Data Flow Diagram Here]}\\[0.4cm]
    Input Frames $\rightarrow$ Feature Extraction $\rightarrow$ Inference $\rightarrow$ Risk Fusion $\rightarrow$ Storage $\rightarrow$ Visualization
    \vspace{1cm}
    }}
    \caption{Data flow across the AEGIS-RS platform.}
\end{figure}
```
