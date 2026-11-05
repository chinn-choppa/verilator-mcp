// Public synthetic SystemVerilog test fixture; Apache-2.0.
module good_top (
    input  logic clk,
    input  logic rst_n,
    output logic q
);
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) q <= 1'b0;
        else        q <= ~q;
    end
endmodule
