package com.wanjie.heti;

import android.app.Activity;
import android.content.res.AssetManager;
import android.graphics.Color;
import android.os.Bundle;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;
import android.widget.TextView;

import com.chaquo.python.Python;
import com.chaquo.python.android.AndroidPlatform;

import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.InetSocketAddress;
import java.net.Socket;
import java.net.URL;

public class MainActivity extends Activity {
    private static final String TAG = "Wanjie";
    private static final int PORT = 8899;

    private WebView webView;
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        webView.setBackgroundColor(Color.WHITE);

        status = new TextView(this);
        status.setText("正在启动本地排盘引擎…\n首次启动需要解压数据，约 2–5 秒");
        status.setTextSize(16);
        status.setTextColor(Color.parseColor("#6b5d33"));
        status.setGravity(Gravity.CENTER);
        status.setBackgroundColor(Color.parseColor("#f7f2e6"));

        root.addView(webView, new FrameLayout.LayoutParams(-1, -1));
        root.addView(status, new FrameLayout.LayoutParams(-1, -1));
        setContentView(root);

        WebSettings s = webView.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setDatabaseEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setBuiltInZoomControls(false);
        s.setDisplayZoomControls(false);
        s.setLoadWithOverviewMode(true);
        s.setUseWideViewPort(true);
        if (BuildConfig.DEBUG) {
            WebView.setWebContentsDebuggingEnabled(true);
        }

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageFinished(WebView view, String url) {
                status.setVisibility(View.GONE);
            }
        });

        final File payloadDir = new File(getFilesDir(), "wanjie");
        final File marker = new File(payloadDir, ".payload-" + BuildConfig.VERSION_CODE);

        if (!Python.isStarted()) {
            Python.start(new AndroidPlatform(getApplicationContext()));
        }

        new Thread(() -> {
            try {
                if (!marker.exists()) {
                    deleteRecursively(payloadDir);
                    if (!payloadDir.mkdirs()) {
                        throw new IOException("无法创建数据目录 " + payloadDir);
                    }
                    copyAssetDir("wanjie", payloadDir);
                    if (!marker.createNewFile()) {
                        throw new IOException("无法写入版本标记");
                    }
                }
                Python py = Python.getInstance();
                Object result = py.getModule("android_boot")
                        .callAttr("start", payloadDir.getAbsolutePath())
                        .toJava(String.class);
                Log.i(TAG, "python boot: " + result);
                if (!waitForServer(45000)) {
                    throw new IOException("本地服务 45 秒内未就绪");
                }
                runOnUiThread(() -> {
                    status.setText("正在打开页面…");
                    webView.loadUrl("http://127.0.0.1:" + PORT + "/");
                });
            } catch (Throwable e) {
                Log.e(TAG, "startup failed", e);
                runOnUiThread(() -> {
                    status.setVisibility(View.VISIBLE);
                    status.setText("启动失败：" + e.getMessage()
                            + "\n\n请把本页截图反馈；若反复失败，可在系统设置中清除应用数据后重试。");
                    status.setOnClickListener(v -> recreate());
                });
            }
        }, "wanjie-start").start();
    }

    private boolean waitForServer(long timeoutMs) {
        long deadline = System.currentTimeMillis() + timeoutMs;
        while (System.currentTimeMillis() < deadline) {
            if (isPortOpen() && isHealthOk()) {
                return true;
            }
            try {
                Thread.sleep(250);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        return false;
    }

    private boolean isPortOpen() {
        try (Socket socket = new Socket()) {
            socket.connect(new InetSocketAddress("127.0.0.1", PORT), 300);
            return true;
        } catch (IOException e) {
            return false;
        }
    }

    private boolean isHealthOk() {
        HttpURLConnection conn = null;
        try {
            conn = (HttpURLConnection) new URL("http://127.0.0.1:" + PORT + "/api/health").openConnection();
            conn.setConnectTimeout(1500);
            conn.setReadTimeout(4000);
            conn.setUseCaches(false);
            return conn.getResponseCode() == 200;
        } catch (IOException e) {
            return false;
        } finally {
            if (conn != null) conn.disconnect();
        }
    }

    private void copyAssetDir(String assetPath, File dest) throws IOException {
        AssetManager am = getAssets();
        String[] children = am.list(assetPath);
        if (children != null && children.length > 0) {
            if (!dest.exists() && !dest.mkdirs()) {
                throw new IOException("无法创建目录 " + dest);
            }
            for (String child : children) {
                copyAssetDir(assetPath + "/" + child, new File(dest, child));
            }
        } else {
            File parent = dest.getParentFile();
            if (parent != null && !parent.exists() && !parent.mkdirs()) {
                throw new IOException("无法创建目录 " + parent);
            }
            try (InputStream in = am.open(assetPath);
                 OutputStream out = new FileOutputStream(dest)) {
                byte[] buf = new byte[65536];
                int n;
                while ((n = in.read(buf)) > 0) {
                    out.write(buf, 0, n);
                }
            }
        }
    }

    private void deleteRecursively(File file) {
        if (file == null || !file.exists()) return;
        File[] children = file.listFiles();
        if (children != null) {
            for (File child : children) deleteRecursively(child);
        }
        //noinspection ResultOfMethodCallIgnored
        file.delete();
    }

    @Override
    public void onBackPressed() {
        if (webView != null && webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onDestroy() {
        if (webView != null) {
            webView.stopLoading();
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
