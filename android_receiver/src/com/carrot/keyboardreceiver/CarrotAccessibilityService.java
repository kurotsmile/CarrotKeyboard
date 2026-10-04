package com.carrot.keyboardreceiver;

import android.accessibilityservice.AccessibilityService;
import android.accessibilityservice.GestureDescription;
import android.graphics.Canvas;
import android.graphics.Color;
import android.graphics.Paint;
import android.graphics.PixelFormat;
import android.graphics.Path;
import android.graphics.Rect;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.Settings;
import android.util.DisplayMetrics;
import android.view.Gravity;
import android.view.Surface;
import android.view.View;
import android.view.WindowManager;
import android.view.accessibility.AccessibilityNodeInfo;
import android.view.accessibility.AccessibilityEvent;

import org.json.JSONObject;

public class CarrotAccessibilityService extends AccessibilityService {
    private static CarrotAccessibilityService instance;
    private static final String PREFS_NAME = "carrot_keyboard";
    private static final String PREF_CLICK_MODE = "click_mode";
    private static final String PREF_MOUSE_ENABLED = "mouse_enabled";
    private static final int CLICK_MODE_SMART = 0;
    private static final int CLICK_MODE_GESTURE = 1;
    private static final int CLICK_MODE_BOTH = 2;
    private static final int CURSOR_SIZE = 64;
    private static final int DRAG_THRESHOLD_PX = 28;
    private float lastX = 0.5f;
    private float lastY = 0.5f;
    private int dragStartX = 0;
    private int dragStartY = 0;
    private long dragStartTime = 0L;
    private boolean dragging = false;
    private WindowManager windowManager;
    private View cursorView;
    private WindowManager.LayoutParams cursorParams;

    public static boolean isReady() {
        return instance != null;
    }

    public static void handle(JSONObject event) {
        if (instance != null) {
            new Handler(Looper.getMainLooper()).post(() -> instance.handleEvent(event));
        }
    }

    public static void refreshMouseControl() {
        if (instance != null) {
            new Handler(Looper.getMainLooper()).post(instance::syncCursorOverlay);
        }
    }

    @Override
    public void onServiceConnected() {
        instance = this;
        syncCursorOverlay();
    }

    @Override
    public void onDestroy() {
        if (instance == this) {
            instance = null;
        }
        removeCursorOverlay();
        super.onDestroy();
    }

    @Override
    public void onAccessibilityEvent(AccessibilityEvent event) {
    }

    @Override
    public void onInterrupt() {
    }

    private void handleEvent(JSONObject event) {
        String device = event.optString("device", "keyboard");
        if ("mouse".equals(device)) {
            if (!isMouseControlEnabled()) {
                removeCursorOverlay();
                dragging = false;
                return;
            }
            handleMouse(event);
        } else if ("system".equals(device)) {
            handleSystem(event);
        } else {
            handleKeyboard(event);
        }
    }

    private void handleSystem(JSONObject event) {
        if ("rotate".equals(event.optString("action", ""))) {
            toggleRotation();
        }
    }

    private void toggleRotation() {
        if (!Settings.System.canWrite(this)) {
            return;
        }

        int current = Settings.System.getInt(
            getContentResolver(),
            Settings.System.USER_ROTATION,
            Surface.ROTATION_0
        );
        int next = (current == Surface.ROTATION_0 || current == Surface.ROTATION_180)
            ? Surface.ROTATION_90
            : Surface.ROTATION_0;

        Settings.System.putInt(getContentResolver(), Settings.System.ACCELEROMETER_ROTATION, 0);
        Settings.System.putInt(getContentResolver(), Settings.System.USER_ROTATION, next);
    }

    private void handleMouse(JSONObject event) {
        String action = event.optString("action", "");
        if (event.has("x_ratio")) {
            lastX = (float) clamp(event.optDouble("x_ratio", lastX));
            lastY = (float) clamp(event.optDouble("y_ratio", lastY));
        }

        int x = Math.round(lastX * (getScreenWidth() - 1));
        int y = Math.round(lastY * (getScreenHeight() - 1));
        moveCursorOverlay(x, y);

        if ("press".equals(action)) {
            dragStartX = x;
            dragStartY = y;
            dragStartTime = System.currentTimeMillis();
            dragging = true;
        } else if ("release".equals(action)) {
            pulseCursor();
            if (dragging && distance(dragStartX, dragStartY, x, y) > DRAG_THRESHOLD_PX) {
                swipeBetween(dragStartX, dragStartY, x, y, dragStartTime);
            } else {
                tap(x, y);
            }
            dragging = false;
        } else if ("scroll".equals(action)) {
            int dy = event.optInt("dy", 0);
            swipeScroll(x, y, dy);
        }
    }

    private void handleKeyboard(JSONObject event) {
        if (!"press".equals(event.optString("action", ""))) {
            return;
        }

        JSONObject key = event.optJSONObject("key");
        if (key == null) {
            return;
        }

        if ("char".equals(key.optString("type"))) {
            String value = key.optString("char", "");
            if (!value.isEmpty()) {
                appendText(value);
            }
            return;
        }

        String name = key.optString("name", "");
        if ("space".equals(name)) {
            appendText(" ");
        } else if ("enter".equals(name)) {
            appendText("\n");
        } else if ("tab".equals(name)) {
            appendText("\t");
        } else if ("backspace".equals(name) || "delete".equals(name)) {
            backspace();
        } else if ("esc".equals(name)) {
            performGlobalAction(GLOBAL_ACTION_BACK);
        } else if ("home".equals(name)) {
            performGlobalAction(GLOBAL_ACTION_HOME);
        }
    }

    private void appendText(String value) {
        AccessibilityNodeInfo node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node == null) {
            return;
        }
        CharSequence current = node.getText();
        String next = (current == null ? "" : current.toString()) + value;
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, next);
        node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
    }

    private void backspace() {
        AccessibilityNodeInfo node = findFocus(AccessibilityNodeInfo.FOCUS_INPUT);
        if (node == null) {
            performGlobalAction(GLOBAL_ACTION_BACK);
            return;
        }
        CharSequence current = node.getText();
        if (current == null || current.length() == 0) {
            return;
        }
        String text = current.toString();
        String next = text.substring(0, text.offsetByCodePoints(text.length(), -1));
        Bundle args = new Bundle();
        args.putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, next);
        node.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args);
    }

    private void tap(int x, int y) {
        int clickMode = getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getInt(PREF_CLICK_MODE, CLICK_MODE_SMART);
        if (clickMode == CLICK_MODE_GESTURE) {
            tapGesture(x, y);
            return;
        }

        boolean clickedNode = clickNodeAt(x, y);
        if (clickMode == CLICK_MODE_BOTH) {
            new Handler(Looper.getMainLooper()).postDelayed(() -> tapGesture(x, y), 90);
            return;
        }
        if (clickedNode) {
            return;
        }

        tapGesture(x, y);
    }

    private void tapGesture(int x, int y) {
        Path path = new Path();
        path.moveTo(x, y);
        GestureDescription gesture = new GestureDescription.Builder()
            .addStroke(new GestureDescription.StrokeDescription(path, 0, 120))
            .build();
        dispatchGesture(gesture, null, null);
    }

    private boolean clickNodeAt(int x, int y) {
        AccessibilityNodeInfo node = findDeepestNodeAt(getRootInActiveWindow(), x, y);
        while (node != null) {
            if (node.isVisibleToUser() && node.isEnabled() && node.isClickable()) {
                if (node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                    return true;
                }
            }
            node = node.getParent();
        }
        return false;
    }

    private AccessibilityNodeInfo findDeepestNodeAt(AccessibilityNodeInfo node, int x, int y) {
        if (node == null || !node.isVisibleToUser()) {
            return null;
        }

        Rect bounds = new Rect();
        node.getBoundsInScreen(bounds);
        if (!bounds.contains(x, y)) {
            return null;
        }

        for (int i = node.getChildCount() - 1; i >= 0; i--) {
            AccessibilityNodeInfo child = node.getChild(i);
            AccessibilityNodeInfo match = findDeepestNodeAt(child, x, y);
            if (match != null) {
                return match;
            }
        }

        return node;
    }

    private void swipeScroll(int x, int y, int dy) {
        if (dy == 0) {
            return;
        }
        int distance = Math.max(180, Math.min(520, Math.abs(dy) * 140));
        int startY = y;
        int endY = dy > 0 ? y + distance : y - distance;
        startY = Math.max(40, Math.min(getScreenHeight() - 40, startY));
        endY = Math.max(40, Math.min(getScreenHeight() - 40, endY));

        Path path = new Path();
        path.moveTo(x, startY);
        path.lineTo(x, endY);
        GestureDescription gesture = new GestureDescription.Builder()
            .addStroke(new GestureDescription.StrokeDescription(path, 0, 220))
            .build();
        dispatchGesture(gesture, null, null);
    }

    private void swipeBetween(int startX, int startY, int endX, int endY, long startTime) {
        Path path = new Path();
        path.moveTo(startX, startY);
        path.lineTo(endX, endY);
        long duration = Math.max(180L, Math.min(700L, System.currentTimeMillis() - startTime));
        GestureDescription gesture = new GestureDescription.Builder()
            .addStroke(new GestureDescription.StrokeDescription(path, 0, duration))
            .build();
        dispatchGesture(gesture, null, null);
    }

    private double distance(int startX, int startY, int endX, int endY) {
        int dx = endX - startX;
        int dy = endY - startY;
        return Math.sqrt(dx * dx + dy * dy);
    }

    private int getScreenWidth() {
        DisplayMetrics metrics = getResources().getDisplayMetrics();
        return Math.max(metrics.widthPixels, 1);
    }

    private int getScreenHeight() {
        DisplayMetrics metrics = getResources().getDisplayMetrics();
        return Math.max(metrics.heightPixels, 1);
    }

    private void createCursorOverlay() {
        if (cursorView != null) {
            return;
        }
        windowManager = (WindowManager) getSystemService(WINDOW_SERVICE);
        cursorView = new CursorView(this);
        cursorParams = new WindowManager.LayoutParams(
            CURSOR_SIZE,
            CURSOR_SIZE,
            WindowManager.LayoutParams.TYPE_ACCESSIBILITY_OVERLAY,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE
                | WindowManager.LayoutParams.FLAG_NOT_TOUCHABLE
                | WindowManager.LayoutParams.FLAG_LAYOUT_NO_LIMITS,
            PixelFormat.TRANSLUCENT
        );
        cursorParams.gravity = Gravity.TOP | Gravity.LEFT;
        cursorParams.x = Math.round(lastX * getScreenWidth()) - CURSOR_SIZE / 2;
        cursorParams.y = Math.round(lastY * getScreenHeight()) - CURSOR_SIZE / 2;

        try {
            windowManager.addView(cursorView, cursorParams);
        } catch (Exception ignored) {
        }
    }

    private void syncCursorOverlay() {
        if (isMouseControlEnabled()) {
            createCursorOverlay();
        } else {
            removeCursorOverlay();
            dragging = false;
        }
    }

    private boolean isMouseControlEnabled() {
        return getSharedPreferences(PREFS_NAME, MODE_PRIVATE).getBoolean(PREF_MOUSE_ENABLED, true);
    }

    private void removeCursorOverlay() {
        if (windowManager != null && cursorView != null) {
            try {
                windowManager.removeView(cursorView);
            } catch (Exception ignored) {
            }
        }
        cursorView = null;
        cursorParams = null;
        windowManager = null;
    }

    private void moveCursorOverlay(int x, int y) {
        if (windowManager == null || cursorView == null || cursorParams == null) {
            return;
        }
        cursorParams.x = x - CURSOR_SIZE / 2;
        cursorParams.y = y - CURSOR_SIZE / 2;
        try {
            windowManager.updateViewLayout(cursorView, cursorParams);
        } catch (Exception ignored) {
        }
    }

    private void pulseCursor() {
        if (cursorView == null) {
            return;
        }
        cursorView.animate()
            .scaleX(1.45f)
            .scaleY(1.45f)
            .alpha(0.65f)
            .setDuration(80)
            .withEndAction(() -> cursorView.animate()
                .scaleX(1f)
                .scaleY(1f)
                .alpha(1f)
                .setDuration(120)
                .start())
            .start();
    }

    private double clamp(double value) {
        return Math.max(0.0, Math.min(1.0, value));
    }

    private static class CursorView extends View {
        private final Paint fillPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
        private final Paint strokePaint = new Paint(Paint.ANTI_ALIAS_FLAG);

        CursorView(CarrotAccessibilityService service) {
            super(service);
            fillPaint.setColor(Color.argb(210, 76, 175, 80));
            strokePaint.setColor(Color.WHITE);
            strokePaint.setStyle(Paint.Style.STROKE);
            strokePaint.setStrokeWidth(6f);
        }

        @Override
        protected void onDraw(Canvas canvas) {
            super.onDraw(canvas);
            float center = getWidth() / 2f;
            canvas.drawCircle(center, center, center - 5f, fillPaint);
            canvas.drawCircle(center, center, center - 7f, strokePaint);
        }
    }
}
