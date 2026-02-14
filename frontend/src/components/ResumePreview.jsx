export default function ResumePreview({ resume, setResume, highlightedItemIds }) {
    const isHighlighted = (id) => highlightedItemIds?.includes(id);

    const handleEditItem = (sectionId, itemId, newText) => {
        setResume((prev) => {
            if (!prev) return prev;
            const updatedSections = prev.sections.map((section) => {
                if (section.id !== sectionId) return section;
                const newItems = section.items.map((it) =>
                    it.id === itemId ? { ...it, text: newText } : it
                );
                return { ...section, items: newItems };
            });
            return { ...prev, sections: updatedSections };
        });
    };

    return (
        <div>
            {resume.sections.map((section) => (
                <div key={section.id} style={{ marginBottom: "1rem" }}>
                    <h3 style={{ textTransform: "uppercase", marginBottom: "0.3rem" }}>
                        {section.title}
                    </h3>
                    <ul style={{ marginLeft: "1.2rem" }}>
                        {section.items.map((item) => (
                            <li
                                key={item.id}
                                data-item-id={item.id}
                                style={{ marginBottom: "0.2rem" }}
                            >
                                <EditableLine
                                    value={item.text}
                                    onChange={(value) => handleEditItem(section.id, item.id, value)}
                                    highlighted={isHighlighted(item.id)}
                                />
                            </li>
                        ))}
                    </ul>
                </div>
            ))}
        </div>
    );
}

function EditableLine({ value, onChange, highlighted }) {
    return (
        <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            rows={1}
            style={{
                width: "100%",
                border: "none",
                resize: "none",
                background: highlighted ? "#fef08a" : "transparent",
                borderLeft: highlighted ? "3px solid #eab308" : "none",
                paddingLeft: highlighted ? "6px" : "0",
                borderRadius: highlighted ? "4px" : "0",
                fontSize: "0.95rem",
                lineHeight: "1.3rem",
                transition: "background 0.3s ease",
            }}
            onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = e.target.scrollHeight + "px";
            }}
        />
    );
}
