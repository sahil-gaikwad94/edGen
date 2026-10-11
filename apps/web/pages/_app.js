import Head from "next/head";
import "../styles/globals.css";

export default function App({ Component, pageProps }) {
  return (
    <>
      <Head>
        <title>EdGen — verified-practice learning</title>
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="description" content="One personal learner model that teaches, tests, diagnoses and plans. Every number computed by code, every claim carries a receipt." />
        <link rel="manifest" href="/manifest.json" />
      </Head>
      <Component {...pageProps} />
    </>
  );
}
