export default function HealthPage() {
  return <div>OK</div>
}

export async function GET() {
  return new Response('OK', { status: 200 })
}