import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { api } from '../lib/api';

export default function Settings() {
  const [twoFactorEnabled, setTwoFactorEnabled] = useState<boolean | null>(
    null
  );
  const [qrCode, setQrCode] = useState<string | null>(null);
  const [setupToken, setSetupToken] = useState('');
  const [message, setMessage] = useState('');
  const [loadingSetup, setLoadingSetup] = useState(false);
  const { accessToken } = useAuth();

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await api('/api/auth/me', {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        setTwoFactorEnabled(res.user.twoFactorEnabled);
      } catch {
        setTwoFactorEnabled(null);
      }
    };
    if (accessToken) fetchStatus();
  }, [accessToken]);

  const startSetup = async () => {
    setLoadingSetup(true);
    try {
      const res = await api('/api/auth/2fa/setup', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      setQrCode(res.qrCode);
    } catch {
      setMessage('Failed to start 2FA setup.');
    } finally {
      setLoadingSetup(false);
    }
  };

  const verifySetup = async () => {
    try {
      await api('/api/auth/2fa/verify-setup', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
        body: JSON.stringify({ token: setupToken }),
      });
      setMessage('2FA setup complete');
      setTwoFactorEnabled(true);
      setQrCode(null);
      setSetupToken('');
    } catch {
      setMessage('Invalid 2FA token');
    }
  };

  const disable2FA = async () => {
    try {
      await api('/api/auth/2fa/disable', {
        method: 'POST',
        headers: { Authorization: `Bearer ${accessToken}` },
      });
      setTwoFactorEnabled(false);
      setMessage('2FA disabled');
    } catch {
      setMessage('Failed to disable 2FA.');
    }
  };

  return (
    <div className="max-w-md mx-auto p-4 bg-white shadow rounded mt-12">
      <h1 className="text-xl font-semibold mb-4">Settings</h1>

      {twoFactorEnabled ? (
        <div>
          <p className="mb-4 text-green-700">2FA is enabled</p>
          <button
            onClick={disable2FA}
            className="bg-red-600 text-white px-4 py-2 rounded hover:bg-red-700"
          >
            Disable 2FA
          </button>
        </div>
      ) : (
        <div>
          <p className="mb-4 text-yellow-700">2FA is not enabled</p>
          {qrCode ? (
            <div>
              <img
                src={qrCode}
                alt="Scan QR for 2FA"
                className="mb-4"
                width={200}
                height={200}
              />
              <input
                type="text"
                placeholder="Enter token"
                value={setupToken}
                onChange={(e) => setSetupToken(e.target.value)}
                className="w-full px-3 py-2 border rounded mb-2"
              />
              <button
                onClick={verifySetup}
                className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 w-full"
              >
                Verify and Enable 2FA
              </button>
            </div>
          ) : (
            <button
              onClick={startSetup}
              className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
              disabled={loadingSetup}
            >
              {loadingSetup ? 'Loading...' : 'Enable 2FA'}
            </button>
          )}
        </div>
      )}

      {message && <p className="mt-4 text-sm text-gray-700">{message}</p>}
    </div>
  );
}
