interface LoadingStateProps {
  message?: string
}

export function LoadingState({
  message = 'Analyzing — this may take a few seconds…',
}: LoadingStateProps) {
  return (
    <div className="loading-state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <p>{message}</p>
    </div>
  )
}
