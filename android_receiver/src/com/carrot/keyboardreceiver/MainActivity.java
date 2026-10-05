package com.carrot.keyboardreceiver;

import android.app.Activity;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.provider.Settings;
import android.graphics.Typeface;
import android.view.Gravity;
import android.view.Surface;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.Inet4Address;
import java.net.InetAddress;
import java.net.NetworkInterface;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Collections;

public class MainActivity extends Activity {
    private static final int DEFAULT_PORT = 50505;
    private static final String PREFS_NAME = "carrot_keyboard";
    private static final String PREF_CLICK_MODE = "click_mode";
    private static final String PREF_MOUSE_ENABLED = "mouse_enabled";
    private static final String PREF_ROTATION_DEGREES = "rotation_degrees";
    private static final int CLICK_MODE_SMART = 0;
    private static final int CLICK_MODE_GESTURE = 1;
    private static final int CLICK_MODE_BOTH = 2;

    private TextView statusView;
    private TextView logView;
    private Button startButton;
    private Button mouseButton;
    private ServerThread serverThread;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        buildUi();
        updateStatus();
    }

    @Override
    protected void onDestroy() {
        stopServer();
        super.onDestroy();
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(32, 32, 32, 32);

        TextView title = new TextView(this);
        title.setText("CarrotKeyboard Receiver");
        title.setTextSize(24);
        title.setTypeface(Typeface.DEFAULT_BOLD);
        root.addView(title);

        statusView = new TextView(this);
        statusView.setTextSize(15);
        statusView.setPadding(0, 18, 0, 18);
        root.addView(statusView);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setOrientation(LinearLayout.VERTICAL);
        buttons.setGravity(Gravity.LEFT);

        startButton = new Button(this);
        startButton.setText("Start");
        startButton.setOnClickListener(v -> toggleServer());
        buttons.addView(startButton);

        Button accessibilityButton = new Button(this);
        accessibilityButton.setText("Accessibility");
        accessibilityButton.setOnClickListener(v -> startActivity(new Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS)));
        buttons.addView(accessibilityButton);

        Button rotationButton = new Button(this);
        rotationButton.setText("Rotation Permission");
        rotationButton.setOnClickListener(v -> openRotationPermission());
        buttons.addView(rotationButton);

        Button rotateScreenButton = new Button(this);
        rotateScreenButton.setText("Rotate Screen");
        rotateScreenButton.setOnClickListener(v -> rotateScreen());
        buttons.addView(rotateScreenButton);

        Button clickModeButton = new Button(this);
        clickModeButton.setText("Click Mode");
        clickModeButton.setOnClickListener(v -> cycleClickMode());
        buttons.addView(clickModeButton);

        mouseButton = new Button(this);
        mouseButton.setOnClickListener(v -> toggleMouseControl());
        buttons.addView(mouseButton);

        root.addView(buttons);

        logView = new TextView(this);
        logView.setTextSize(13);
        logView.setTextIsSelectable(true);

        ScrollView scroll = new ScrollView(this);
        scroll.addView(logView);
        root.addView(scroll, new LinearLayout.LayoutParams(
            LinearLayout.LayoutParams.MATCH_PARENT,
            0,
            1
        ));

        setContentView(root);
    }

    private void toggleServer() {
        if (serverThread != null) {
            stopServer();
        } else {
            startServer();
        }
    }

    private void startServer() {
        serverThread = new ServerThread(DEFAULT_PORT);
        serverThread.start();
        startButton.setText("Stop");
        updateStatus();
        appendLog("Listening on " + getIpAddress() + ":" + DEFAULT_PORT);
    }

    private void stopServer() {
        if (serverThread != null) {
            serverThread.shutdown();
            serverThread = null;
        }
        if (startButton != null) {
            startButton.setText("Start");
        }
        updateStatus();
    }

    private void updateStatus() {
        String status = "Phone IP: " + getIpAddress() + "\n"
            + "Port: " + DEFAULT_PORT + "\n"
            + "Accessibility Service: " + (CarrotAccessibilityService.isReady() ? "Enabled" : "Not enabled") + "\n"
            + "Rotation Permission: " + (Settings.System.canWrite(this) ? "Allowed" : "Not allowed") + "\n"
            + "Rotation: " + getRotationDegrees() + "°\n"
            + "Mouse Control: " + (isMouseControlEnabled() ? "On" : "Off") + "\n"
            + "Click Mode: " + getClickModeName() + "\n"
            + "Server: " + (serverThread == null ? "Stopped" : "Running");
        statusView.setText(status);
        if (mouseButton != null) {
            mouseButton.setText(isMouseControlEnabled() ? "Turn Mouse Off" : "Turn Mouse On");
        }
    }

    private void openRotationPermission() {
        Intent intent = new Intent(
            Settings.ACTION_MANAGE_WRITE_SETTINGS,
            Uri.parse("package:" + getPackageName())
        );
        startActivity(intent);
    }

    private void cycleClickMode() {
        int current = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getInt(PREF_CLICK_MODE, CLICK_MODE_SMART);
        int next = current == CLICK_MODE_SMART
            ? CLICK_MODE_GESTURE
            : current == CLICK_MODE_GESTURE ? CLICK_MODE_BOTH : CLICK_MODE_SMART;
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(PREF_CLICK_MODE, next)
            .apply();
        appendLog("Click Mode: " + getClickModeName(next));
        updateStatus();
    }

    private void rotateScreen() {
        if (!Settings.System.canWrite(this)) {
            appendLog("Rotation Permission: Not allowed");
            openRotationPermission();
            return;
        }

        int nextDegrees = nextRotationDegrees(getRotationDegrees());
        applyRotation(nextDegrees);
        appendLog("Rotation: " + nextDegrees + "°");
        updateStatus();
    }

    private void toggleMouseControl() {
        boolean enabled = !isMouseControlEnabled();
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putBoolean(PREF_MOUSE_ENABLED, enabled)
            .apply();
        CarrotAccessibilityService.refreshMouseControl();
        appendLog("Mouse Control: " + (enabled ? "On" : "Off"));
        updateStatus();
    }

    private boolean isMouseControlEnabled() {
        return getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getBoolean(PREF_MOUSE_ENABLED, true);
    }

    private int getRotationDegrees() {
        int saved = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getInt(PREF_ROTATION_DEGREES, -1);
        if (saved == 0 || saved == 90 || saved == 180 || saved == 270) {
            return saved;
        }
        return degreesForSurfaceRotation(Settings.System.getInt(
            getContentResolver(),
            Settings.System.USER_ROTATION,
            Surface.ROTATION_0
        ));
    }

    private int nextRotationDegrees(int currentDegrees) {
        if (currentDegrees == 0) {
            return 90;
        }
        if (currentDegrees == 90) {
            return 180;
        }
        if (currentDegrees == 180) {
            return 270;
        }
        return 0;
    }

    private void applyRotation(int degrees) {
        Settings.System.putInt(getContentResolver(), Settings.System.ACCELEROMETER_ROTATION, 0);
        Settings.System.putInt(getContentResolver(), Settings.System.USER_ROTATION, surfaceRotationForDegrees(degrees));
        getSharedPreferences(PREFS_NAME, MODE_PRIVATE)
            .edit()
            .putInt(PREF_ROTATION_DEGREES, degrees)
            .apply();
    }

    private int surfaceRotationForDegrees(int degrees) {
        if (degrees == 90) {
            return Surface.ROTATION_90;
        }
        if (degrees == 180) {
            return Surface.ROTATION_180;
        }
        if (degrees == 270) {
            return Surface.ROTATION_270;
        }
        return Surface.ROTATION_0;
    }

    private int degreesForSurfaceRotation(int rotation) {
        if (rotation == Surface.ROTATION_90) {
            return 90;
        }
        if (rotation == Surface.ROTATION_180) {
            return 180;
        }
        if (rotation == Surface.ROTATION_270) {
            return 270;
        }
        return 0;
    }

    private String getClickModeName() {
        int mode = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getInt(PREF_CLICK_MODE, CLICK_MODE_SMART);
        return getClickModeName(mode);
    }

    private String getClickModeName(int mode) {
        if (mode == CLICK_MODE_GESTURE) {
            return "Gesture";
        }
        if (mode == CLICK_MODE_BOTH) {
            return "Smart + Gesture";
        }
        return "Smart";
    }

    private String getIpAddress() {
        try {
            for (NetworkInterface networkInterface : Collections.list(NetworkInterface.getNetworkInterfaces())) {
                for (InetAddress address : Collections.list(networkInterface.getInetAddresses())) {
                    if (!address.isLoopbackAddress() && address instanceof Inet4Address) {
                        return address.getHostAddress();
                    }
                }
            }
        } catch (Exception ignored) {
        }
        return "0.0.0.0";
    }

    private void appendLog(String line) {
        runOnUiThread(() -> {
            logView.append(line + "\n");
            updateStatus();
        });
    }

    private class ServerThread extends Thread {
        private final int port;
        private volatile boolean running = true;
        private ServerSocket serverSocket;

        ServerThread(int port) {
            this.port = port;
        }

        @Override
        public void run() {
            try {
                serverSocket = new ServerSocket(port);
                while (running) {
                    Socket socket = serverSocket.accept();
                    appendLog("Mac connected: " + socket.getInetAddress().getHostAddress());
                    handleClient(socket);
                    appendLog("Mac disconnected");
                }
            } catch (Exception exc) {
                if (running) {
                    appendLog("Server error: " + exc.getMessage());
                }
            }
        }

        void shutdown() {
            running = false;
            try {
                if (serverSocket != null) {
                    serverSocket.close();
                }
            } catch (Exception ignored) {
            }
        }

        private void handleClient(Socket socket) {
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(socket.getInputStream()))) {
                String line;
                while (running && (line = reader.readLine()) != null) {
                    JSONObject event = new JSONObject(line);
                    CarrotAccessibilityService.handle(event);
                    if ("system".equals(event.optString("device", "")) && "rotate".equals(event.optString("action", ""))) {
                        appendLog("Rotation command");
                    }
                }
            } catch (Exception exc) {
                appendLog("Client error: " + exc.getMessage());
            } finally {
                try {
                    socket.close();
                } catch (Exception ignored) {
                }
            }
        }
    }
}
