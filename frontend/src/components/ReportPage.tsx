import React, { useEffect, useState } from 'react';

const ReportPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [authenticated, setAuthenticated] = useState(false);
  const [username, setUsername] = useState<string>('');
  const [reportJson, setReportJson] = useState<string>('');
  const [error, setError] = useState<string | null>(null);

  const apiUrl = process.env.REACT_APP_API_URL || 'http://localhost:8000';

  const checkAuth = async () => {
    try {
      setCheckingAuth(true);
      const response = await fetch(`${apiUrl}/auth/me`, {
        credentials: 'include',
      });
      if (!response.ok) {
        setAuthenticated(false);
        setUsername('');
        return;
      }

      const payload = await response.json();
      setAuthenticated(Boolean(payload?.authenticated));
      setUsername(payload?.user?.preferred_username || '');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to verify session');
    } finally {
      setCheckingAuth(false);
    }
  };

  useEffect(() => {
    void checkAuth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const login = () => {
    window.location.href = `${apiUrl}/auth/login`;
  };

  const logout = async () => {
    await fetch(`${apiUrl}/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    });
    setAuthenticated(false);
    setUsername('');
    setReportJson('');
  };

  const downloadReport = async () => {
    try {
      setLoading(true);
      setError(null);
      setReportJson('');

      const response = await fetch(`${apiUrl}/reports`, {
        credentials: 'include',
      });
      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const payload = await response.json();
      setReportJson(JSON.stringify(payload, null, 2));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (checkingAuth) {
    return <div className="p-8">Checking session...</div>;
  }

  if (!authenticated) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
        <button
          onClick={login}
          className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
        >
          Login via bionicpro-auth
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-100">
      <div className="p-8 bg-white rounded-lg shadow-md">
        <h1 className="text-2xl font-bold mb-6">Usage Reports</h1>
        <p className="mb-4 text-sm text-gray-700">Signed in as: <b>{username || 'unknown'}</b></p>
        
        <div className="flex gap-3">
          <button
            onClick={downloadReport}
            disabled={loading}
            className={`px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 ${
              loading ? 'opacity-50 cursor-not-allowed' : ''
            }`}
          >
            {loading ? 'Generating Report...' : 'Download Report'}
          </button>
          <button
            onClick={logout}
            className="px-4 py-2 bg-gray-500 text-white rounded hover:bg-gray-600"
          >
            Logout
          </button>
        </div>

        {error && (
          <div className="mt-4 p-4 bg-red-100 text-red-700 rounded">
            {error}
          </div>
        )}

        {reportJson && (
          <pre className="mt-4 p-4 text-xs bg-gray-100 rounded overflow-x-auto">{reportJson}</pre>
        )}
      </div>
    </div>
  );
};

export default ReportPage;