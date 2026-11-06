// Original public RTL test fixture; Apache-2.0.
module counter #(parameter int WIDTH = 8) (
    input  logic             clk,
    input  logic             rst_n,
    output logic [WIDTH-1:0] count
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) count <= '0;
        else        count <= count + 1'b1;
    end
endmodule
