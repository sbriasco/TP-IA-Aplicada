import { navigate, useRoute } from "./navigation";
import { JobPreviewPage } from "./pages/JobPreviewPage";
import { SceneEditorPage } from "./pages/SceneEditorPage";
import { SessionDetailPage } from "./pages/SessionDetailPage";
import { SessionsPage } from "./pages/SessionsPage";

export function App() {
  const route = useRoute();

  switch (route.name) {
    case "job":
      return <JobPreviewPage jobId={route.jobId} />;
    case "sessions":
      return <SessionsPage />;
    case "session":
      return <SessionDetailPage key={route.sessionId} sessionId={route.sessionId} />;
    case "editor":
      return <SceneEditorPage key={route.sessionId} sessionId={route.sessionId} />;
    case "not_found":
      return (
        <main>
          <h1>Página no encontrada</h1>
          <button type="button" onClick={() => navigate("/")}>
            Volver a las sesiones
          </button>
        </main>
      );
  }
}
