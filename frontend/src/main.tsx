import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

/** Last line of defense: a rendering bug must degrade to a readable message
 *  with a reload button — never a black screen. */
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { error: Error | null }
> {
  state = { error: null as Error | null }
  static getDerivedStateFromError(error: Error) {
    return { error }
  }
  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, maxWidth: 560, margin: '0 auto', fontFamily: 'sans-serif' }}>
          <h2 style={{ color: '#ff7a7f' }}>The interface hit a rendering error</h2>
          <p style={{ color: '#c6d0de' }}>
            The agent and server are fine — this is a display bug. The error was:
          </p>
          <pre style={{ color: '#8e9aad', whiteSpace: 'pre-wrap', fontSize: 13 }}>
            {String(this.state.error)}
          </pre>
          <button
            onClick={() => location.reload()}
            style={{ padding: '10px 20px', cursor: 'pointer', fontSize: 14 }}
          >
            Reload
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <ErrorBoundary>
      <App />
    </ErrorBoundary>
  </React.StrictMode>,
)
