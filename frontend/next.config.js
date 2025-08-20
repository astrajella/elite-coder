/** Next.js config - simple rewrites to proxy API calls to services **/
module.exports = {
  async rewrites() {
    return [
      { source: '/api/agent/:path*', destination: 'http://localhost:8001/:path*' },
      { source: '/api/retrieval/:path*', destination: 'http://localhost:8002/:path*' },
      { source: '/api/ledger/:path*', destination: 'http://localhost:8003/:path*' }
    ]
  }
}
