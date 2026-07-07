import React, { useState } from 'react'

function App() {
  const [count, setCount] = useState(0)

  return (
    <div style={{ textAlign: 'center', padding: '50px' }}>
      <h1>🚀 Nexus Core</h1>
      <p>5G Network-in-a-Box Control Plane</p>
      <p>Stack: React + Django + Celery + Redis + PostgreSQL</p>
      <div style={{ padding: '20px' }}>
        <button onClick={() => setCount((count) => count + 1)}>
          Count: {count}
        </button>
      </div>
      <hr />
      <p>Status: Deployed to GitHub Pages</p>
    </div>
  )
}

export default App
