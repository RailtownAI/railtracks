const width = 900;
const height = 500;

const nodes = [
    { id: "Node", x: 150, y: 250, url: "node", description: "Core execution units that handle tasks", color: "#6366f1" },
    { id: "Runner", x: 350, y: 250, url: "runner", description: "Orchestrates node execution and workflow", color: "#8b5cf6" },
    { id: "PubSub", x: 550, y: 150, url: "pubsub", description: "Message passing and event coordination", color: "#06b6d4" },
    { id: "Coordinator", x: 550, y: 250, url: "coordinator", description: "Manages system-wide coordination", color: "#10b981" },
    { id: "RTState", x: 550, y: 350, url: "rtstate", description: "Maintains application state", color: "#f59e0b" }
];

const links = [
    { source: "Node", target: "Runner", color: "#8b5cf6" },
    { source: "Runner", target: "PubSub", color: "#06b6d4" },
    { source: "Runner", target: "Coordinator", color: "#10b981" },
    { source: "Runner", target: "RTState", color: "#f59e0b" }
];

const svg = d3.select("#rt-architecture-diagram")
    .append("svg")
    .attr("width", width)
    .attr("height", height)
    .style("background", "linear-gradient(135deg, #f8fafc 0%, #e2e8f0 100%)")
    .style("border-radius", "12px")
    .style("box-shadow", "0 4px 6px -1px rgba(0, 0, 0, 0.1)");

// Add gradient definitions
const defs = svg.append("defs");

// Create gradients for each node
nodes.forEach(node => {
    const gradient = defs.append("linearGradient")
        .attr("id", `gradient-${node.id}`)
        .attr("x1", "0%").attr("y1", "0%")
        .attr("x2", "100%").attr("y2", "100%");
    
    gradient.append("stop")
        .attr("offset", "0%")
        .attr("stop-color", node.color);
    
    gradient.append("stop")
        .attr("offset", "100%")
        .attr("stop-color", d3.color(node.color).darker(0.5));
});

// Enhanced arrowhead
defs.append("marker")
    .attr("id", "arrowhead")
    .attr("viewBox", "0 -5 10 10")
    .attr("refX", 8)
    .attr("refY", 0)
    .attr("markerWidth", 8)
    .attr("markerHeight", 8)
    .attr("orient", "auto")
    .append("path")
    .attr("d", "M0,-5L10,0L0,5")
    .attr("fill", "#64748b");

// Draw links with animation
const linkElements = svg.selectAll(".link")
    .data(links)
    .enter().append("line")
    .attr("class", "link")
    .attr("x1", d => nodes.find(n => n.id === d.source).x)
    .attr("y1", d => nodes.find(n => n.id === d.source).y)
    .attr("x2", d => nodes.find(n => n.id === d.source).x)
    .attr("y2", d => nodes.find(n => n.id === d.source).y)
    .attr("stroke", d => d.color)
    .attr("stroke-width", 3)
    .attr("stroke-opacity", 0.7)
    .attr("marker-end", "url(#arrowhead)")
    .transition()
    .duration(1000)
    .delay((d, i) => i * 200)
    .attr("x2", d => nodes.find(n => n.id === d.target).x)
    .attr("y2", d => nodes.find(n => n.id === d.target).y);

// Draw nodes with enhanced styling
const nodeGroups = svg.selectAll(".node")
    .data(nodes)
    .enter().append("g")
    .attr("class", "node")
    .attr("transform", d => `translate(${d.x},${d.y})`)
    .style("cursor", "pointer")
    .on("click", (event, d) => window.location.href = d.url)
    .on("mouseover", function(event, d) {
        d3.select(this).select("rect")
            .transition()
            .duration(200)
            .attr("transform", "scale(1.1)");
    })
    .on("mouseout", function(d) {
        d3.select(this).select("rect")
            .transition()
            .duration(200)
            .attr("transform", "scale(1)");
    });

// Add node rectangles with gradients
nodeGroups.append("rect")
    .attr("width", 100)
    .attr("height", 50)
    .attr("x", -50)
    .attr("y", -25)
    .attr("rx", 8)
    .attr("fill", d => `url(#gradient-${d.id})`)
    .attr("stroke", "white")
    .attr("stroke-width", 2)
    .style("opacity", 0)
    .transition()
    .duration(800)
    .delay((d, i) => i * 150)
    .style("opacity", 1);

// Add node text
nodeGroups.append("text")
    .attr("text-anchor", "middle")
    .attr("dy", "0.35em")
    .attr("fill", "white")
    .attr("font-family", "'Inter', 'SF Pro Display', system-ui, sans-serif")
    .attr("font-size", "14px")
    .attr("font-weight", "600")
    .style("text-shadow", "0 1px 2px rgba(0,0,0,0.3)")
    .text(d => d.id)
    .style("opacity", 0)
    .transition()
    .duration(800)
    .delay((d, i) => i * 150 + 200)
    .style("opacity", 1);
