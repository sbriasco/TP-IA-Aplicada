interface SessionDetailPageProps {
  sessionId: string;
}

export function SessionDetailPage({ sessionId }: SessionDetailPageProps) {
  return (
    <main>
      <h1>Sesión</h1>
      <p>{sessionId}</p>
    </main>
  );
}
