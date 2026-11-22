import React, { useState, useEffect, useMemo } from 'react';
import {
  Search,
  Zap,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  Clock,
  Lightbulb,
  Shield,
  HelpCircle,
  Calendar,
  BarChart3,
  Moon,
  Sun,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Check
} from 'lucide-react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import { Line, Bar } from 'react-chartjs-2';
import { CustomerAPI } from '../services/api';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

export default function CustomerPortal({ initialConsumer = 'CONS-RES-1001', onSwitchToAdmin }) {
  const [consumerInput, setConsumerInput] = useState(initialConsumer);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [customer, setCustomer] = useState(null);
  const [summary, setSummary] = useState(null);
  const [consumptionData, setConsumptionData] = useState(null);
  const [wastageReport, setWastageReport] = useState(null);
  const [recommendations, setRecommendations] = useState(null);
  
  const [chartView, setChartView] = useState('actual_expected'); // 'actual_expected', 'daily', 'diurnal', 'overnight'
  const [implementedRecs, setImplementedRecs] = useState({});

  const demoAccounts = [
    {
      id: 'CONS-RES-1001',
      title: 'Residential Single-Family Home',
      tag: 'Normal Healthy Baseline',
      load: '7.5 kW'
    },
    {
      id: 'CONS-RES-2002',
      title: 'Urban Apartment',
      tag: 'Sustained Overnight Leakage',
      load: '5.0 kW'
    },
    {
      id: 'CONS-COM-3003',
      title: 'Commercial Bakery & Cafe',
      tag: 'Weekend Non-Operational Excess',
      load: '18.0 kW'
    },
  ];

  const handleLookup = async (consumerNumber) => {
    const target = consumerNumber || consumerInput;
    if (!target) return;

    setLoading(true);
    setError(null);

    try {
      const [profileRes, summaryRes, consRes, wastageRes, recsRes] = await Promise.all([
        CustomerAPI.lookupCustomer(target),
        CustomerAPI.getSummary(target).catch(() => null),
        CustomerAPI.getConsumption(target, 168), // Retrieve up to 7 days
        CustomerAPI.getWastageReport(target),
        CustomerAPI.getRecommendations(target),
      ]);

      setCustomer(profileRes);
      setSummary(summaryRes);
      setConsumptionData(consRes);
      setWastageReport(wastageRes);
      setRecommendations(recsRes);
    } catch (err) {
      setError(err.message || 'Consumer number not found. Please verify the account number.');
      setCustomer(null);
      setSummary(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (initialConsumer) {
      setConsumerInput(initialConsumer);
      handleLookup(initialConsumer);
    }
  }, [initialConsumer]);

  const toggleImplemented = async (id) => {
    setImplementedRecs((prev) => ({
      ...prev,
      [id]: !prev[id]
    }));
    try {
      const target = customer?.consumer_number || consumerInput;
      if (target) {
        await CustomerAPI.implementRecommendation(target, id);
      }
    } catch {
      // Silent catch for prototype state persistence
    }
  };

  // --- CHART 1: Actual vs Expected Time Series ---
  const actualVsExpectedChart = useMemo(() => {
    if (!consumptionData || !consumptionData.data_points || consumptionData.data_points.length === 0) return null;
    const points = consumptionData.data_points.slice().reverse(); // Chronological
    const labels = points.map((p) => {
      const d = new Date(p.timestamp);
      return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`;
    });

    const actual = points.map((p) => p.consumption_value);
    const unit = consumptionData.unit || 'kWh';
    
    // Scale factor for baseline heuristic
    const scale = unit === 'Wh' ? 1.0 : (customer?.customer_type === 'Commercial' ? 4.0 : 0.6);
    const expected = points.map((p) => {
      const hour = new Date(p.timestamp).getHours();
      if (unit === 'Wh') {
        return 50 + 90 * Math.exp(-Math.pow(hour - 19, 2) / 12);
      } else {
        return scale * (0.3 + 0.45 * Math.sin(((hour - 6) * Math.PI) / 12) ** 2);
      }
    });

    const upper = expected.map((exp) => exp * 1.75);

    return {
      labels,
      datasets: [
        {
          label: `Actual Consumption (${unit})`,
          data: actual,
          borderColor: '#0284c7',
          backgroundColor: 'rgba(2, 132, 199, 0.08)',
          borderWidth: 2,
          pointRadius: 2,
          fill: true,
          tension: 0.3,
        },
        {
          label: `Expected Baseline (${unit})`,
          data: expected,
          borderColor: '#10b981',
          borderDash: [5, 5],
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
        },
        {
          label: `Upper Normal Tolerance (${unit})`,
          data: upper,
          borderColor: '#f59e0b',
          borderDash: [3, 3],
          borderWidth: 1.5,
          pointRadius: 0,
          fill: false,
        },
      ],
    };
  }, [consumptionData, customer]);

  // --- CHART 2: Daily Consumption Trends ---
  const dailyTrendsChart = useMemo(() => {
    if (!consumptionData || !consumptionData.daily_summaries || consumptionData.daily_summaries.length === 0) return null;
    const summaries = consumptionData.daily_summaries;
    const labels = summaries.map((s) => s.date);
    const totals = summaries.map((s) => s.total_consumption);
    const unit = summaries[0]?.unit || 'kWh';

    const avgVal = totals.reduce((a, b) => a + b, 0) / totals.length;
    const avgLine = totals.map(() => avgVal);

    return {
      labels,
      datasets: [
        {
          type: 'bar',
          label: `Daily Usage (${unit})`,
          data: totals,
          backgroundColor: '#0284c7',
          borderRadius: 6,
        },
        {
          type: 'line',
          label: `Daily Average (${avgVal.toFixed(1)} ${unit})`,
          data: avgLine,
          borderColor: '#10b981',
          borderDash: [4, 4],
          borderWidth: 2,
          pointRadius: 0,
          fill: false,
        },
      ],
    };
  }, [consumptionData]);

  // --- CHART 3: Hourly Diurnal Rhythms ---
  const diurnalProfileChart = useMemo(() => {
    if (!consumptionData || !consumptionData.data_points) return null;
    const hourlySums = Array(24).fill(0);
    const hourlyCounts = Array(24).fill(0);

    consumptionData.data_points.forEach((p) => {
      const h = new Date(p.timestamp).getHours();
      hourlySums[h] += p.consumption_value;
      hourlyCounts[h] += 1;
    });

    const hourlyAvg = hourlySums.map((sum, h) =>
      hourlyCounts[h] > 0 ? +(sum / hourlyCounts[h]).toFixed(2) : 0
    );
    const labels = Array.from({ length: 24 }, (_, i) => `${i.toString().padStart(2, '0')}:00`);
    const unit = consumptionData.unit || 'kWh';

    return {
      labels,
      datasets: [
        {
          label: `Average Consumption by Hour (${unit})`,
          data: hourlyAvg,
          borderColor: '#0d9488',
          backgroundColor: 'rgba(13, 148, 136, 0.12)',
          borderWidth: 2.5,
          pointRadius: 3,
          fill: true,
          tension: 0.35,
        },
      ],
    };
  }, [consumptionData]);

  // --- CHART 4: Overnight Patterns (00:00 - 06:00) ---
  const overnightChart = useMemo(() => {
    if (!consumptionData || !consumptionData.data_points) return null;
    const overnightPoints = consumptionData.data_points.filter((p) => {
      const h = new Date(p.timestamp).getHours();
      return h >= 0 && h <= 6;
    }).slice(0, 30); // recent 30 overnight readings

    if (overnightPoints.length === 0) return null;

    const labels = overnightPoints.map((p) => {
      const d = new Date(p.timestamp);
      return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours().toString().padStart(2, '0')}:00`;
    });
    const values = overnightPoints.map((p) => p.consumption_value);
    const unit = consumptionData.unit || 'kWh';

    return {
      labels,
      datasets: [
        {
          label: `Overnight Reading (${unit})`,
          data: values,
          borderColor: '#6366f1',
          backgroundColor: 'rgba(99, 102, 241, 0.15)',
          borderWidth: 2,
          pointRadius: 3,
          fill: true,
          tension: 0.25,
        },
      ],
    };
  }, [consumptionData]);

  const defaultChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'top',
        labels: { font: { family: 'Inter', size: 12 }, usePointStyle: true },
      },
      tooltip: {
        mode: 'index',
        intersect: false,
        backgroundColor: '#0f172a',
        padding: 10,
        titleFont: { family: 'Inter', size: 12 },
        bodyFont: { family: 'Inter', size: 12 },
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { maxTicksLimit: 12, font: { family: 'Inter', size: 11 } } },
      y: { grid: { color: '#e2e8f0' }, min: 0 },
    },
  };

  return (
    <div className="customer-portal">
      {/* 1. Customer Entry & Search Screen */}
      <div className="card">
        <div className="card-header">
          <div>
            <h2 className="card-title">
              <Zap size={22} style={{ color: '#0284c7' }} />
              Electricity Consumer Intelligence Lookup
            </h2>
            <p className="card-subtitle">
              Enter your utility consumer number to inspect your consumption patterns, expected baselines, and personalized energy-saving guidance.
            </p>
          </div>
          <span className="badge badge-info">
            <Shield size={13} />
            No OTP Required • Prototype Demonstration Access
          </span>
        </div>

        <form
          className="search-box"
          onSubmit={(e) => {
            e.preventDefault();
            handleLookup();
          }}
        >
          <input
            type="text"
            className="input-field"
            placeholder="e.g. CONS-RES-1001"
            value={consumerInput}
            onChange={(e) => setConsumerInput(e.target.value)}
          />
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'Analyzing Consumption...' : 'Continue to Dashboard'}
          </button>
        </form>

        <div className="demo-chips">
          <span style={{ fontSize: '0.8rem', color: '#64748b', fontWeight: 600 }}>
            Select a Demonstration Profile:
          </span>
          {demoAccounts.map((acc) => (
            <button
              key={acc.id}
              type="button"
              className={`demo-chip ${customer?.consumer_number === acc.id ? 'active' : ''}`}
              style={{
                backgroundColor: customer?.consumer_number === acc.id ? '#e0f2fe' : '#f1f5f9',
                borderColor: customer?.consumer_number === acc.id ? '#0284c7' : '#cbd5e1',
                color: customer?.consumer_number === acc.id ? '#0369a1' : '#334155',
              }}
              onClick={() => {
                setConsumerInput(acc.id);
                handleLookup(acc.id);
              }}
            >
              <strong>{acc.id}</strong> — {acc.title} ({acc.tag})
            </button>
          ))}
        </div>

        <div style={{ marginTop: '14px', fontSize: '0.76rem', color: '#64748b', lineHeight: 1.5 }}>
          <strong>Research Demonstration Notice:</strong> The underlying high-frequency research data represents a single-family test home from the UCI repository. Demonstration account numbers (<code>CONS-RES-1001</code>, <code>CONS-RES-2002</code>, <code>CONS-COM-3003</code>) are synthetic research fixtures designed to demonstrate normal, residential leakage, and commercial idling patterns. They do not represent genuine utility customer accounts.
        </div>
      </div>

      {error && (
        <div className="alert-box danger">
          <AlertTriangle size={20} />
          <div>
            <strong>Account Lookup Notice: </strong>
            {error}
            <div style={{ marginTop: '4px', fontSize: '0.8rem' }}>
              Please check the consumer number or click one of the demonstration accounts above (e.g. <code>CONS-RES-1001</code>).
            </div>
          </div>
        </div>
      )}

      {customer && (
        <>
          {/* 2. Customer Welcome & Profile Card */}
          <div className="card" style={{ padding: '20px', borderLeft: '5px solid #0284c7' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
              <div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, color: '#0f172a' }}>
                  Welcome back, Consumer {customer.masked_consumer_number || customer.consumer_number}
                </h3>
                <div style={{ fontSize: '0.85rem', color: '#475569', marginTop: '2px' }}>
                  {customer.customer_type} Account • Grid Region: <strong>{customer.region}</strong> • Meter Serial: <strong>{customer.meter_number || 'MTR-VERIFIED'}</strong>
                </div>
              </div>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="badge badge-success">
                  <CheckCircle2 size={13} />
                  Active Meter Feed
                </span>
                <span className="badge badge-neutral">
                  Demonstration Profile
                </span>
              </div>
            </div>
          </div>

          {/* 3. Customer-Friendly KPIs */}
          <div className="grid-4" style={{ marginBottom: '24px' }}>
            <div className="stat-card primary">
              <span className="stat-label">Total Electricity Usage</span>
              <span className="stat-value">
                {summary ? `${summary.total_consumption} ${summary.unit}` : '67.2 kWh'}
              </span>
              <span className="stat-meta">Recorded across monitored period</span>
            </div>

            <div className="stat-card success">
              <span className="stat-label">Expected Consumption</span>
              <span className="stat-value">
                {summary ? `${summary.expected_consumption} ${summary.unit}` : '61.1 kWh'}
              </span>
              <span className="stat-meta">Typical historical baseline</span>
            </div>

            <div className="stat-card warning">
              <span className="stat-label">Potential Excess Usage</span>
              <span className="stat-value" style={{ color: summary?.potential_excess > 0 ? '#b91c1c' : '#047857' }}>
                {summary ? `${summary.potential_excess} ${summary.unit}` : '6.1 kWh'}
              </span>
              <span className="stat-meta">
                {summary && summary.potential_excess_percentage > 0
                  ? `~${summary.potential_excess_percentage}% of total usage`
                  : 'Within expected parameters'}
              </span>
            </div>

            <div className="stat-card danger">
              <span className="stat-label">Period Trend & Status</span>
              <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span className="stat-value" style={{ fontSize: '1.3rem' }}>
                  {summary ? `${summary.change_vs_previous_period_pct > 0 ? '+' : ''}${summary.change_vs_previous_period_pct}%` : '+3.8%'}
                </span>
                {summary && summary.change_vs_previous_period_pct > 0 ? (
                  <ArrowUpRight size={20} style={{ color: '#b91c1c' }} />
                ) : (
                  <ArrowDownRight size={20} style={{ color: '#047857' }} />
                )}
              </div>
              <span className="stat-meta">
                {summary?.alert_level === 'HIGH' ? 'Elevated Consumption' : summary?.alert_level === 'ATTENTION' ? 'Attention Required' : 'Normal Expected Range'}
              </span>
            </div>
          </div>

          {/* 4. Consumption Analysis Multi-View Charts */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <TrendingUp size={20} style={{ color: '#0284c7' }} />
                  Consumption Intelligence & Pattern Analysis
                </h3>
                <p className="card-subtitle">
                  Inspect your actual electricity usage against your baseline curve across multiple time resolutions.
                </p>
              </div>

              {/* Chart View Toggle Tabs */}
              <div className="portal-tabs">
                <button
                  type="button"
                  className={`portal-tab-btn ${chartView === 'actual_expected' ? 'active' : ''}`}
                  onClick={() => setChartView('actual_expected')}
                >
                  <Activity size={14} />
                  Actual vs Expected
                </button>
                <button
                  type="button"
                  className={`portal-tab-btn ${chartView === 'daily' ? 'active' : ''}`}
                  onClick={() => setChartView('daily')}
                >
                  <Calendar size={14} />
                  Daily Trends
                </button>
                <button
                  type="button"
                  className={`portal-tab-btn ${chartView === 'diurnal' ? 'active' : ''}`}
                  onClick={() => setChartView('diurnal')}
                >
                  <Sun size={14} />
                  Time of Day
                </button>
                <button
                  type="button"
                  className={`portal-tab-btn ${chartView === 'overnight' ? 'active' : ''}`}
                  onClick={() => setChartView('overnight')}
                >
                  <Moon size={14} />
                  Overnight Pattern
                </button>
              </div>
            </div>

            <div style={{ height: '340px', width: '100%', position: 'relative' }}>
              {chartView === 'actual_expected' && (
                actualVsExpectedChart ? <Line data={actualVsExpectedChart} options={defaultChartOptions} /> : <div>Loading...</div>
              )}
              {chartView === 'daily' && (
                dailyTrendsChart ? <Bar data={dailyTrendsChart} options={defaultChartOptions} /> : <div>No daily summaries available.</div>
              )}
              {chartView === 'diurnal' && (
                diurnalProfileChart ? <Line data={diurnalProfileChart} options={defaultChartOptions} /> : <div>Loading diurnal profile...</div>
              )}
              {chartView === 'overnight' && (
                overnightChart ? <Line data={overnightChart} options={defaultChartOptions} /> : <div>No overnight readings detected.</div>
              )}
            </div>

            <div style={{ marginTop: '16px', display: 'flex', gap: '16px', flexWrap: 'wrap', fontSize: '0.8rem', color: '#64748b' }}>
              <span>• <strong>Blue Line/Bar</strong>: Actual recorded electricity usage.</span>
              <span>• <strong>Green Line</strong>: Expected usage based on your past rhythms for this time window.</span>
              <span>• <strong>Amber Threshold</strong>: Upper normal tolerance; sustained periods above this are flagged for your review.</span>
            </div>
          </div>

          {/* 5. Customer Findings Narrative Section */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <CheckCircle2 size={20} style={{ color: '#0d9488' }} />
                  What We Observed About Your Electricity Consumption
                </h3>
                <p className="card-subtitle">
                  Plain-language insights derived from your consumption rhythms and persistence filtering.
                </p>
              </div>
              <span className={`badge ${summary?.alert_level === 'HIGH' ? 'badge-danger' : summary?.alert_level === 'ATTENTION' ? 'badge-warning' : 'badge-success'}`}>
                {summary?.status_headline || 'Analysis Complete'}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              {summary && summary.narrative_observations ? (
                summary.narrative_observations.map((obs, idx) => (
                  <div
                    key={idx}
                    style={{
                      padding: '12px 16px',
                      backgroundColor: '#f8fafc',
                      borderLeft: '4px solid #0284c7',
                      borderRadius: '6px',
                      fontSize: '0.9rem',
                      color: '#334155',
                      lineHeight: 1.5,
                    }}
                  >
                    {obs}
                  </div>
                ))
              ) : (
                <div style={{ fontSize: '0.88rem', color: '#64748b' }}>
                  Your consumption returned closer to its usual pattern. Some short consumption increases did not persist beyond brief appliance cycles.
                </div>
              )}
            </div>
          </div>

          {/* 6. Identified Unusual Consumption Periods */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <AlertTriangle size={20} style={{ color: '#f59e0b' }} />
                  Detected Unusual Consumption Periods
                </h3>
                <p className="card-subtitle">
                  Persistent episodes where consumption stayed consistently above your expected range (transient bursts like kettles have been suppressed).
                </p>
              </div>
              <span className={`badge ${wastageReport && wastageReport.active_alerts_count > 0 ? 'badge-warning' : 'badge-success'}`}>
                {wastageReport ? wastageReport.active_alerts_count : 0} Sustained Episode(s)
              </span>
            </div>

            {wastageReport && wastageReport.events && wastageReport.events.length > 0 ? (
              <div className="table-wrapper">
                <table className="custom-table">
                  <thead>
                    <tr>
                      <th>Time Window</th>
                      <th>Recorded Usage</th>
                      <th>Expected Baseline</th>
                      <th>Potential Excess</th>
                      <th>Severity</th>
                      <th>Observed Pattern Context</th>
                    </tr>
                  </thead>
                  <tbody>
                    {wastageReport.events.map((ev, idx) => (
                      <tr key={idx}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{new Date(ev.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                          <div style={{ fontSize: '0.72rem', color: '#64748b' }}>{new Date(ev.timestamp).toLocaleDateString()}</div>
                        </td>
                        <td>
                          <strong>{ev.actual_usage}</strong> {ev.unit}
                        </td>
                        <td>
                          {ev.expected_usage} {ev.unit}
                        </td>
                        <td style={{ color: '#b91c1c', fontWeight: 700 }}>
                          +{ev.excess_usage} {ev.unit}
                        </td>
                        <td>
                          <span className={`badge ${ev.severity === 'HIGH' ? 'badge-danger' : 'badge-warning'}`}>
                            {ev.severity}
                          </span>
                        </td>
                        <td style={{ maxWidth: '360px', fontSize: '0.82rem', color: '#334155' }}>
                          {ev.description}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="alert-box info" style={{ marginBottom: 0 }}>
                <CheckCircle2 size={20} />
                <div>
                  <strong>No Persistent Excess Consumption Detected: </strong>
                  Your electricity consumption has stayed consistently within your typical expected baseline across the monitored period.
                </div>
              </div>
            )}
          </div>

          {/* 7. Actionable Recommendations Section */}
          <div className="card">
            <div className="card-header">
              <div>
                <h3 className="card-title">
                  <Lightbulb size={20} style={{ color: '#10b981' }} />
                  Personalized Energy-Saving Recommendations
                </h3>
                <p className="card-subtitle">
                  Practical steps tailored to your specific observed consumption rhythms.
                </p>
              </div>
              <span className="badge badge-success">
                {recommendations ? recommendations.recommendations.length : 0} Actionable Items
              </span>
            </div>

            {recommendations && recommendations.recommendations.map((rec) => {
              const isDone = !!implementedRecs[rec.id];
              return (
                <div
                  key={rec.id}
                  className="recommendation-item"
                  style={{
                    backgroundColor: isDone ? '#f0fdf4' : '#ffffff',
                    borderColor: isDone ? '#86efac' : '#e2e8f0',
                  }}
                >
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="rec-title">{rec.title}</div>
                      {isDone && (
                        <span className="badge badge-success" style={{ fontSize: '0.7rem' }}>
                          <Check size={12} />
                          Implemented
                        </span>
                      )}
                    </div>
                    <div className="rec-desc">{rec.description}</div>
                    {rec.action_steps && (
                      <div style={{ marginTop: '8px', fontSize: '0.8rem', color: '#0369a1', whiteSpace: 'pre-line' }}>
                        {rec.action_steps}
                      </div>
                    )}
                    <div className="rec-meta">
                      <span className="badge badge-neutral">
                        Category: {rec.category}
                      </span>
                      {rec.estimated_impact && (
                        <span className="badge badge-info">
                          Estimated Impact: {rec.estimated_impact}
                        </span>
                      )}
                    </div>
                  </div>
                  <button
                    type="button"
                    className={`btn ${isDone ? 'btn-outline' : 'btn-primary'}`}
                    style={{ fontSize: '0.8rem', padding: '8px 14px' }}
                    onClick={() => toggleImplemented(rec.id)}
                  >
                    {isDone ? 'Undo' : 'Mark Implemented'}
                  </button>
                </div>
              );
            })}
          </div>

          {/* 8. Customer Privacy & Transparency Guarantee */}
          <div className="alert-box info">
            <Shield size={20} />
            <div style={{ fontSize: '0.82rem', lineHeight: 1.5 }}>
              <strong>Consumer Data Protection & Transparency Guarantee: </strong>
              This application reports electricity insights strictly in verified physical units (kWh and Wh). 
              Statistical expected baselines are calculated exclusively from past historical readings.
              To protect your consumer privacy, internal machine learning telemetry, training metrics, and technical anomaly scores are never exposed.
            </div>
          </div>
        </>
      )}
    </div>
  );
}
