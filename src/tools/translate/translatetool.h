// SPDX-License-Identifier: GPL-3.0-or-later
// SPDX-FileCopyrightText: 2026 Brian Barrett

#pragma once

#include "tools/abstractactiontool.h"

// Button that asks the editor to OCR the selection and paint English over
// its Simplified Chinese. The work happens in CaptureWidget::translate(),
// because only the editor can add objects to the undo stack.
class TranslateTool : public AbstractActionTool
{
    Q_OBJECT
public:
    explicit TranslateTool(QObject* parent = nullptr);

    bool closeOnButtonPressed() const override;

    QIcon icon(const QColor& background, bool inEditor) const override;
    QString name() const override;
    QString description() const override;

    CaptureTool* copy(QObject* parent = nullptr) override;

protected:
    CaptureTool::Type type() const override;

public slots:
    void pressed(CaptureContext& context) override;
};
