import React, { useEffect, useState } from 'react';
import { useAuth } from '../contexts/AuthContext.new';
import { DashboardProperty, SecureAPI } from '../lib/secureApi';
import { RevenueSummary } from './RevenueSummary';

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];

const DashboardContent: React.FC = () => {
  const [properties, setProperties] = useState<DashboardProperty[] | null>(null);
  const [selectedProperty, setSelectedProperty] = useState('');
  const [year, setYear] = useState('2024');
  const [month, setMonth] = useState('3');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    SecureAPI.getDashboardProperties().then((result) => {
      if (!active) return;
      setProperties(result);
      setSelectedProperty(result[0]?.id || '');
    }).catch(() => {
      if (active) setError('Failed to load your properties. Please refresh to try again.');
    });
    return () => { active = false; };
  }, []);

  const validYear = /^\d{1,4}$/.test(year) && Number(year) >= 1 && Number(year) <= 9998;
  const selected = properties?.find((property) => property.id === selectedProperty);
  const controlClass = 'block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500 text-sm';

  return (
    <div className="p-4 lg:p-6 min-h-full">
      <div className="max-w-7xl mx-auto">
        <h1 className="text-2xl font-bold mb-6 text-gray-900">Property Management Dashboard</h1>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:p-6">
          <h2 className="text-lg lg:text-xl font-medium text-gray-900 mb-2">Revenue Overview</h2>
          <p className="text-sm lg:text-base text-gray-600 mb-6">Revenue by check-in date in the property's local time zone.</p>
          {error ? <p role="alert" className="text-red-600">{error}</p> : properties === null ? (
            <p role="status">Loading your properties...</p>
          ) : properties.length === 0 ? (
            <p>No properties are assigned to your account.</p>
          ) : (
            <>
              <div className="grid sm:grid-cols-3 gap-4 mb-6">
                <div>
                  <label htmlFor="revenue-property" className="block text-xs font-medium text-gray-700 mb-1">Property</label>
                  <select id="revenue-property" value={selectedProperty} onChange={(event) => setSelectedProperty(event.target.value)} className={controlClass}>
                    {properties.map((property) => <option key={property.id} value={property.id}>{property.name}</option>)}
                  </select>
                </div>
                <div>
                  <label htmlFor="revenue-year" className="block text-xs font-medium text-gray-700 mb-1">Year</label>
                  <input id="revenue-year" type="number" min="1" max="9998" step="1" value={year} onChange={(event) => setYear(event.target.value)} className={controlClass} />
                </div>
                <div>
                  <label htmlFor="revenue-month" className="block text-xs font-medium text-gray-700 mb-1">Period</label>
                  <select id="revenue-month" value={month} onChange={(event) => setMonth(event.target.value)} className={controlClass}>
                    <option value="">Full year</option>
                    {MONTHS.map((name, index) => <option key={name} value={index + 1}>{name}</option>)}
                  </select>
                </div>
              </div>
              {selected && <p className="text-sm text-gray-600 mb-4">Time zone: {selected.timezone}</p>}
              {!validYear ? <p role="alert" className="text-red-600">Enter a year from 1 to 9998.</p> : selected && (
                <RevenueSummary key={`${selectedProperty}:${year}:${month}`} propertyId={selectedProperty} year={Number(year)} month={month ? Number(month) : undefined} />
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  return user ? <DashboardContent key={`${user.id}:${user.tenant_id}`} /> : null;
};

export default Dashboard;
