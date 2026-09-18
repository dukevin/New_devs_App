import React, { useEffect, useState } from 'react';
import { DashboardRevenue, SecureAPI } from '../lib/secureApi';
import { formatRevenue } from '../utils/formatRevenue';

interface RevenueSummaryProps {
  propertyId: string;
  year: number;
  month?: number;
}

export const RevenueSummary: React.FC<RevenueSummaryProps> = ({ propertyId, year, month }) => {
  const [data, setData] = useState<DashboardRevenue | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setData(null);
    setError('');
    SecureAPI.getDashboardSummary(propertyId, year, month).then((response) => {
      if (active) setData(response);
    }).catch(() => {
      if (active) setError('Failed to load revenue data. Please refresh or select another period to try again.');
    }).finally(() => {
      if (active) setLoading(false);
    });
    return () => { active = false; };
  }, [propertyId, year, month]);

  if (loading) return <div role="status" className="p-6 bg-gray-50 rounded-lg">Loading revenue...</div>;
  if (error) return <div role="alert" className="p-4 text-red-600 bg-red-50 rounded-lg">{error}</div>;
  if (!data) return null;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
      <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-4">Total Revenue</h2>
      {data.totals.length === 0 ? (
        <div>
          <p className="text-3xl font-bold text-gray-900">0.00</p>
          <p className="text-sm text-gray-600 mt-2">No bookings in this period.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.totals.map((total) => (
            <div key={total.currency}>
              <p className="text-3xl font-bold text-gray-900 tracking-tight">{total.currency} {formatRevenue(total.total_revenue)}</p>
              <p className="text-sm text-gray-600 mt-1">{total.reservations_count} bookings</p>
            </div>
          ))}
        </div>
      )}
      <div className="mt-6 pt-4 border-t border-gray-100">
        <p className="text-xs text-gray-500 font-medium uppercase tracking-wider">Property ID</p>
        <p className="text-sm font-semibold text-gray-700 font-mono mt-1">{data.property_id}</p>
      </div>
    </div>
  );
};
