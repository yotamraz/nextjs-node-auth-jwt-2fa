import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';

export default function TwoFactor() {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [tempToken] = useState(() => localStorage.getItem('tempToken') ?? '');
  const { setAccessToken } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (!tempToken) {
      navigate('/login');
    }
  }, [tempToken, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    try {
      const res = await api('/api/auth/2fa/login', {
        method: 'POST',
        headers: { Authorization: `Bearer ${tempToken}` },
        body: JSON.stringify({ token }),
      });

      setAccessToken(res.accessToken);
      localStorage.removeItem('tempToken');
      navigate('/');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Invalid code');
    }
  };

  return (
    <div className="max-w-sm mx-auto mt-20 p-6 bg-white rounded shadow">
      <h1 className="text-xl font-semibold mb-4">Two-Factor Authentication</h1>
      <form onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Enter 2FA code"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          className="w-full px-3 py-2 border rounded mb-4"
        />
        <button
          type="submit"
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700"
        >
          Verify
        </button>
      </form>
      {error && <p className="text-red-600 mt-4 text-sm">{error}</p>}
    </div>
  );
}
