# Context: Phase 7 - Production Deployment & UI Integration

## Scope Update
- **Phase Split**: The user decided to split this phase due to its heavy workload. **Phase 7 will focus *exclusively* on building the Frontend UI and integrating it locally.** Infrastructure and Deployment (EC2, Vercel, Nginx, SSL) will be deferred to a subsequent phase/step.

## Locked Decisions (Phase 7: Frontend UI)

### 1. Frontend Technology
- **Choice**: Next.js (TypeScript).
- **Rationale**: Provides a professional, commercial-grade UI. It demonstrates strong Software Engineering skills compared to quick internal tools like Streamlit/Gradio. Leveraging the TypeScript/Node.js ecosystem (e.g., Vercel AI SDK) will maximize visual quality and development speed.

### 2. UI Interaction Model
- **Choice**: Hybrid (Split-screen Dashboard).
- **Layout**:
  - **Main Pane (Left)**: Displays the original legal text retrieved (Context Retrieval) with keyword highlighting.
  - **Sidebar (Right)**: Chat interface where the Agent explains the law using the IRAC structure and the user can ask follow-up questions.
- **Rationale**: Matches professional Legal Tech products (like Harvey, Lexis+ AI) to build user trust through direct reference to original text.

## Deferred Decisions (Future Phase: Infrastructure & Deployment)

*These decisions are locked in but will be executed after the local UI integration is complete.*

### 1. Deployment Platform
- **Choice**: Hybrid Model (Frontend on Vercel + Backend on AWS EC2).
- **Rationale**: Cloud Native approach. Vercel handles Next.js hosting (SSL, CDN) with zero-config. EC2 hosts the FastAPI backend and Qdrant database via `docker-compose.yml`, demonstrating practical containerization and cloud infrastructure skills.

### 2. Infrastructure & Security
- **Choice**: Nginx Reverse Proxy + Strict CORS + SSL.
- **Rationale**: Production-ready standards. Nginx sits in front of FastAPI. CORS will be strictly locked to the Vercel frontend domain (e.g., `https://legal-agent.vercel.app`) with no wildcards (`*`). Certbot will be used to secure the backend API with Let's Encrypt SSL, ensuring the HTTPS frontend can communicate with the backend.
